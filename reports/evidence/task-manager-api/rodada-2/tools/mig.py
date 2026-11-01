"""Testes da migração users.auth_nonce (cwd na cópia; banco em <copia>/instance/tasks.db, preparado pelo runner).

Uso: python -I -B mig.py <copia> <passo> <saida.json> <copia_original>
Passos: falha | ingenuo | normal | segunda | leitura_original
Sai com código 1 se a expectativa do passo não for atendida.
"""
import ast
import hashlib
import json
import os
import sqlite3
import sys

COPY, STEP, OUT, ORIG_COPY = sys.argv[1:5]
COPY = os.path.realpath(COPY)
sys.path.insert(0, COPY)
os.chdir(COPY)
DBP = os.path.join(COPY, 'instance', 'tasks.db')


def q(sql, args=()):
    con = sqlite3.connect(DBP)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def columns(t):
    return [r[1] for r in q(f'PRAGMA table_info({t})')]


def snapshot(exclude=('auth_nonce',)):
    snap = {}
    for t in ('users', 'categories', 'tasks'):
        cols = [c for c in columns(t) if c not in exclude]
        snap[t] = q(f'SELECT {",".join(cols)} FROM {t} ORDER BY id')
    return hashlib.sha256(json.dumps(snap, default=str).encode()).hexdigest()


def schema_sql():
    return q('SELECT name, sql FROM sqlite_master ORDER BY name')


def admin_password_from_original_seed():
    tree = ast.parse(open(os.path.join(ORIG_COPY, 'seed.py')).read())
    nodes = sorted((n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.Expr))), key=lambda n: n.lineno)
    var = None
    for n in nodes:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'email' \
                and n.value.value == 'joao@email.com':
            var = n.targets[0].value.id
        if var and isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and getattr(n.value.func, 'attr', '') == \
                'set_password' and n.value.func.value.id == var:
            return n.value.args[0].value
    raise RuntimeError('senha do admin não encontrada no seed original')


result = {'step': STEP}
before = {'cols': columns('users'), 'snap': snapshot(exclude=()), 'snap_sem_nonce': snapshot(), 'schema': schema_sql()}
result['antes_tem_coluna'] = 'auth_nonce' in before['cols']
expected = {}

if STEP == 'falha':
    import secrets
    real = secrets.token_urlsafe
    calls = {'n': 0}

    def failing(n=None):
        calls['n'] += 1
        if calls['n'] == 2:  # depois do ALTER e do 1º UPDATE, durante o preenchimento
            raise RuntimeError('falha induzida no preenchimento')
        return real(n)
    secrets.token_urlsafe = failing
    import app as appmod
    err = None
    try:
        appmod.create_app()
    except Exception as e:  # noqa
        err = type(e).__name__
    secrets.token_urlsafe = real
    result.update({'erro': err, 'chamadas_ao_gerador': calls['n'], 'depois_tem_coluna': 'auth_nonce' in columns('users'),
                   'snapshot_identico': snapshot(exclude=()) == before['snap'], 'schema_identico': schema_sql() == before['schema']})
    expected = {'antes_tem_coluna': False, 'erro': 'RuntimeError', 'chamadas_ao_gerador': 2, 'depois_tem_coluna': False,
                'snapshot_identico': True, 'schema_identico': True}

elif STEP == 'ingenuo':
    # Controle negativo: mesma migração apenas envolvida em engine.begin() (sem BEGIN explícito).
    import secrets
    from sqlalchemy import create_engine
    eng = create_engine('sqlite:///' + DBP)
    err = None
    try:
        with eng.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE users ADD COLUMN auth_nonce VARCHAR(64)')
            ids = [r[0] for r in conn.exec_driver_sql('SELECT id FROM users')]
            for i, uid in enumerate(ids):
                if i == 1:
                    raise RuntimeError('falha induzida no preenchimento')
                conn.exec_driver_sql('UPDATE users SET auth_nonce=? WHERE id=?', (secrets.token_urlsafe(32), uid))
    except RuntimeError as e:
        err = type(e).__name__
    eng.dispose()
    result.update({'erro': err, 'depois_tem_coluna': 'auth_nonce' in columns('users'),
                   'snapshot_identico': snapshot(exclude=()) == before['snap']})
    expected = {'erro': 'RuntimeError', 'depois_tem_coluna': True, 'snapshot_identico': False}

elif STEP in ('normal', 'segunda'):
    import app as appmod
    nonces_before = q('SELECT id, auth_nonce FROM users ORDER BY id') if result['antes_tem_coluna'] else None
    app = appmod.create_app()
    nonces = q('SELECT id, auth_nonce FROM users ORDER BY id')
    result.update({'depois_tem_coluna': 'auth_nonce' in columns('users'), 'usuarios': len(nonces),
                   'nonces_nao_nulos': sum(1 for _, n in nonces if n), 'nonces_distintos': len({n for _, n in nonces if n}),
                   'dados_preservados_exceto_nonce': snapshot() == before['snap_sem_nonce']})
    expected = {'depois_tem_coluna': True, 'usuarios': 3, 'nonces_nao_nulos': 3, 'nonces_distintos': 3,
                'dados_preservados_exceto_nonce': True}
    if STEP == 'segunda':
        result.update({'nonces_inalterados': nonces == nonces_before, 'schema_inalterado': schema_sql() == before['schema']})
        expected.update({'antes_tem_coluna': True, 'nonces_inalterados': True, 'schema_inalterado': True})
    else:
        r = app.test_client().post('/login', json={'email': 'joao@email.com', 'password': admin_password_from_original_seed()})
        h = q("SELECT password FROM users WHERE email='joao@email.com'")[0][0]
        result.update({'login_admin_md5_legado': r.status_code,
                       'hash_admin_apos_login': 'werkzeug-scrypt' if h.startswith('scrypt:') else 'outro',
                       'nonce_admin_inalterado_pelo_login': q('SELECT auth_nonce FROM users WHERE id=1')[0][0] ==
                       [n for i, n in nonces if i == 1][0]})
        expected.update({'antes_tem_coluna': False, 'login_admin_md5_legado': 200,
                         'hash_admin_apos_login': 'werkzeug-scrypt', 'nonce_admin_inalterado_pelo_login': True})

elif STEP == 'leitura_original':
    import app as appmod
    cl = appmod.app.test_client()
    out = {}
    for p in ('/users', '/tasks', '/users/1', '/categories', '/reports/summary'):
        r = cl.get(p)
        body = r.get_json()
        if isinstance(body, dict):
            body.pop('generated_at', None)
        out[p] = {'status': r.status_code, 'digest': hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]}
    result['leituras'] = out
    expected = {}  # comparado pelo runner (base × migrado)

result['falhas'] = [f'{k}: {result.get(k)!r} != {v!r}' for k, v in expected.items() if result.get(k) != v]
with open(OUT, 'w') as fh:
    json.dump(result, fh, indent=1, default=str)
print(json.dumps(result, default=str))
sys.exit(1 if result['falhas'] else 0)
