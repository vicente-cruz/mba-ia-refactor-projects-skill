"""Testes da migração users.auth_nonce (rodar com cwd na cópia).

Uso: python -I -B mig.py <copia> <passo> <saida.json>
Passos: falha | ingenuo | normal | segunda | leitura_original
O banco usado é sempre <copia>/instance/tasks.db, preparado pelo driver.
"""
import hashlib
import json
import os
import sqlite3
import sys

COPY, STEP, OUT = sys.argv[1:4]
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
    return q("SELECT name, sql FROM sqlite_master ORDER BY name")


result = {'step': STEP}
before = {'cols': columns('users'), 'snap': snapshot(exclude=()), 'snap_sem_nonce': snapshot(), 'schema': schema_sql()}
result['antes_tem_coluna'] = 'auth_nonce' in before['cols']

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
    result['erro'] = err
    result['chamadas_ao_gerador'] = calls['n']
    result['depois_tem_coluna'] = 'auth_nonce' in columns('users')
    result['snapshot_identico'] = snapshot(exclude=()) == before['snap']
    result['schema_identico'] = schema_sql() == before['schema']

elif STEP == 'ingenuo':
    # Controle negativo: a mesma migração envolvida só em engine.begin() (sem BEGIN explícito).
    import secrets
    from sqlalchemy import create_engine
    eng = create_engine('sqlite:///' + DBP)
    err = None
    try:
        with eng.begin() as c:
            c.exec_driver_sql('ALTER TABLE users ADD COLUMN auth_nonce VARCHAR(64)')
            ids = [r[0] for r in c.exec_driver_sql('SELECT id FROM users')]
            for i, uid in enumerate(ids):
                if i == 1:
                    raise RuntimeError('falha induzida no preenchimento')
                c.exec_driver_sql('UPDATE users SET auth_nonce=? WHERE id=?', (secrets.token_urlsafe(32), uid))
    except RuntimeError as e:
        err = type(e).__name__
    eng.dispose()
    result['erro'] = err
    result['depois_tem_coluna'] = 'auth_nonce' in columns('users')
    result['snapshot_identico'] = snapshot(exclude=()) == before['snap']

elif STEP in ('normal', 'segunda'):
    import app as appmod
    nonces_before = q('SELECT id, auth_nonce FROM users ORDER BY id') if result['antes_tem_coluna'] else None
    app = appmod.create_app()
    nonces = q('SELECT id, auth_nonce FROM users ORDER BY id')
    result['depois_tem_coluna'] = 'auth_nonce' in columns('users')
    result['usuarios'] = len(nonces)
    result['nonces_nao_nulos'] = sum(1 for _, n in nonces if n)
    result['nonces_distintos'] = len({n for _, n in nonces if n})
    result['dados_preservados_exceto_nonce'] = snapshot() == before['snap_sem_nonce']
    if STEP == 'segunda':
        result['nonces_inalterados'] = nonces == nonces_before
        result['schema_inalterado'] = schema_sql() == before['schema']
    else:
        cl = app.test_client()
        r = cl.post('/login', json={'email': 'joao@email.com', 'password': '<removido>'})
        result['login_admin_md5_legado'] = r.status_code
        h = q("SELECT password FROM users WHERE email='joao@email.com'")[0][0]
        result['hash_admin_apos_login'] = 'werkzeug-scrypt' if h.startswith('scrypt:') else 'outro'
        result['nonce_admin_inalterado_pelo_login'] = q("SELECT auth_nonce FROM users WHERE id=1")[0][0] == \
            [n for i, n in nonces if i == 1][0]

elif STEP == 'leitura_original':
    import app as appmod
    cl = appmod.app.test_client()
    out = {}
    for p in ('/users', '/tasks', '/users/1', '/categories', '/reports/summary'):
        r = cl.get(p)
        body = r.get_json()
        if isinstance(body, dict):
            body.pop('generated_at', None)
        out[p] = {'status': r.status_code,
                  'digest': hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()}
    result['leituras'] = out

with open(OUT, 'w') as fh:
    json.dump(result, fh, indent=1, default=str)
print(json.dumps(result, default=str))
