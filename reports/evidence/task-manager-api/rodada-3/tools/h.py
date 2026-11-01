"""Harness de validação do task-manager-api (rodada 2): original × refatorado.

Uso (feito por run_all.sh): python -I -B h.py <copia> <original|refatorado> <grupo> <saida.json>
Executa com cwd na cópia isolada; nunca no repositório.

Credenciais: no original, lidas do próprio seed.py da cópia (via ast, sem literais aqui);
no refatorado, das variáveis SEED_*_PASSWORD definidas pelo runner. Senhas de cenário
(nova, outra, cadastro, errada) são geradas por execução e nunca gravadas nos resultados.
Código de saída 1 se qualquer expectativa falhar.
"""
import ast
import hashlib
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

COPY, MODE, GROUP, OUT = sys.argv[1:5]
COPY = os.path.realpath(COPY)
TOOLS = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, COPY)
sys.path.insert(1, TOOLS)
os.chdir(COPY)
from expect import evaluate, global_checks  # noqa: E402

ORIG = MODE == 'original'
DBP = os.path.join(COPY, 'instance', 'tasks.db')
SECRETS_FILE = os.path.join(os.path.dirname(os.path.realpath(OUT)), f'segredos-{MODE}.txt')
MISSING = object()
SALT = 'task-manager-auth'
FIXED_TS = None  # definido por now_naive na criação de fixtures
H = 2 ** 63  # primeiro inteiro fora do INTEGER de 64 bits do SQLite
A_EMAIL, M_EMAIL, P_EMAIL = 'joao@email.com', 'maria@email.com', 'pedro@email.com'
WRITE_METHODS = ('POST', 'PUT', 'DELETE', 'PATCH')


def now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fmt(d):
    return d.strftime('%Y-%m-%d %H:%M:%S.%f')


def note_secret(value):
    if value:
        with open(SECRETS_FILE, 'a') as fh:
            fh.write(str(value) + '\n')


# ------------------------------------------------------------------ credenciais
def _original_credentials():
    tree = ast.parse(open(os.path.join(COPY, 'seed.py')).read())
    nodes = sorted((n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.Expr))), key=lambda n: n.lineno)
    emails, creds = {}, {}
    for n in nodes:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'email' \
                and isinstance(n.value, ast.Constant):
            emails[n.targets[0].value.id] = n.value.value
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) \
                and n.value.func.attr == 'set_password' and isinstance(n.value.args[0], ast.Constant):
            creds[emails[n.value.func.value.id]] = n.value.args[0].value
    return creds


if ORIG:
    CRED = _original_credentials()
else:
    CRED = {A_EMAIL: os.environ['SEED_ADMIN_PASSWORD'], M_EMAIL: os.environ['SEED_USER_PASSWORD'],
            P_EMAIL: os.environ['SEED_MANAGER_PASSWORD']}
PW = {k: 'Fx-' + secrets.token_urlsafe(9) for k in ('nova', 'outra', 'cadastro', 'errada', 'nova2')}
for v in list(CRED.values()) + list(PW.values()):
    note_secret(v)
assert len(set(PW.values()) | set(CRED.values())) == len(PW) + len(CRED), 'senhas de cenário devem ser distintas'
SECRET_LABELS = {v: f'<senha:{k}>' for k, v in PW.items()}
SECRET_LABELS.update({v: f'<senha:seed:{e.split("@")[0]}>' for e, v in CRED.items()})

# ------------------------------------------------------------------ app/seed
_APP = None


def make_app(overrides=None):
    global _APP
    import app as appmod
    if ORIG:
        _APP = appmod.app
        return _APP
    if overrides:
        return appmod.create_app(overrides)
    if _APP is None:
        _APP = appmod.create_app()
    return _APP


def run_seed(app):
    import contextlib
    import io
    import seed
    with contextlib.redirect_stdout(io.StringIO()):
        if ORIG:
            seed.seed_data()
        else:
            seed.seed_data(app, seed.read_seed_passwords(os.environ))


# ------------------------------------------------------------------ sqlite direto
def q(sql, args=()):
    con = sqlite3.connect(DBP)
    try:
        rows = con.execute(sql, args).fetchall()
        con.commit()
        return rows
    finally:
        con.close()


def columns(table):
    return [r[1] for r in q(f'PRAGMA table_info({table})')]


def counts():
    return {t: q(f'SELECT COUNT(*) FROM {t}')[0][0] for t in ('tasks', 'users', 'categories')}


def db_state():
    snap = [q(f'SELECT * FROM {t} ORDER BY id') for t in ('users', 'categories', 'tasks')]
    return hashlib.sha256(json.dumps(snap, default=str).encode()).hexdigest()[:20]


def hash_kind(email):
    rows = q('SELECT password FROM users WHERE email=?', (email,))
    if not rows:
        return None
    h = rows[0][0] or ''
    if len(h) == 32 and all(ch in '0123456789abcdef' for ch in h):
        return 'md5'
    return 'werkzeug-scrypt' if h.startswith('scrypt:') else 'outro'


def nonce_of(uid):
    if 'auth_nonce' not in columns('users'):
        return None
    r = q('SELECT auth_nonce FROM users WHERE id=?', (uid,))
    return r[0][0] if r else None


# ------------------------------------------------------------------ sanitização
def sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ('password', 'auth_nonce'):
                out[k] = '<presente>'  # a presença é verificada; o valor nunca é gravado
            elif k == 'token':
                note_secret(v)
                out[k] = '<fake-token>' if isinstance(v, str) and v.startswith('fake-jwt-token-') else (
                    '<token>' if isinstance(v, str) and v else v)
            else:
                out[k] = sanitize(v)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, str) and obj in SECRET_LABELS:
        return SECRET_LABELS[obj]
    return obj


def merge(base, extra):
    if base is None:
        return None
    out = json.loads(json.dumps(base))
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        elif isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = out[k] + v
        else:
            out[k] = v
    return out


def S(status, error=MISSING, **kw):
    spec = {'status': status}
    if error is not MISSING:
        spec['error'] = error
    spec.update(kw)
    return spec


def REJ(status, msg, write=True, **kw):
    spec = S(status, msg, **kw)
    if write:
        spec['unchanged'] = True
    return spec


# ------------------------------------------------------------------ contexto
class Ctx:
    def __init__(self):
        self.app = make_app()
        self.client = self.app.test_client()
        self.tokens = {}
        self.records = []
        self.names = set()

    def reseed(self, login=True):
        run_seed(self.app)
        if login:
            self.login_all()

    def login(self, email, pw):
        r = self.client.post('/login', json={'email': email, 'password': pw})
        tok = (r.get_json(silent=True) or {}).get('token')
        note_secret(tok)
        return tok

    def login_all(self):
        self.tokens = {'A': self.login(A_EMAIL, CRED[A_EMAIL]), 'M': self.login(M_EMAIL, CRED[M_EMAIL]),
                       'P': self.login(P_EMAIL, CRED[P_EMAIL])}

    def bearer(self, key):
        return {'Authorization': f'Bearer {self.tokens[key]}'}

    def raw(self, method, path, body=MISSING, raw=None, ctype=None, hdr=None):
        kw = {}
        if raw is not None:
            kw['data'] = raw
            kw['content_type'] = ctype or 'application/json'
        elif body is not MISSING:
            kw['data'] = json.dumps(body)
            kw['content_type'] = 'application/json'
        r = self.client.open(path, method=method, headers=hdr or {}, **kw)
        ct = r.headers.get('Content-Type', '')
        res = {'status': r.status_code, 'is_json': 'application/json' in ct}
        js = r.get_json(silent=True) if 'json' in ct else None
        if js is not None:
            res['json'] = sanitize(js)
        else:
            res['text'] = r.get_data(as_text=True)[:60]
        if r.headers.get('WWW-Authenticate'):
            res['www_authenticate'] = r.headers['WWW-Authenticate']
        if r.headers.get('Allow'):
            res['allow'] = sorted(x.strip() for x in r.headers['Allow'].split(','))
        return res

    def _add(self, rec, spec):
        assert rec['name'] not in self.names, f'caso duplicado: {rec["name"]}'
        self.names.add(rec['name'])
        rec['exp'] = spec
        rec['errs'] = evaluate(spec, rec) + global_checks(rec, MODE)
        self.records.append(rec)

    def case(self, name, method, path, body=MISSING, raw=None, ctype=None, hdr=None, exp=None, exp_o=None,
             exp_r=None, r_more=None, o_more=None, cls=None, qc=False, reseed=False, setup=None, post=None,
             only=None):
        if only and only != MODE:
            return None
        if reseed:
            self.reseed()
        if setup:
            setup(self)
        if isinstance(hdr, str):
            hdr = self.bearer(hdr)
        write = method in WRITE_METHODS
        pre_view = post(self) if (write and post) else None  # visão pública antes da requisição
        pre = db_state() if write else None
        at_utc, at_local = now_naive(), datetime.now()
        n_q = None
        if qc:
            from database import db
            from sqlalchemy import event
            with self.app.app_context():
                eng = db.engine
            cnt = [0]

            def cb(*a, **k):
                cnt[0] += 1
            event.listen(eng, 'before_cursor_execute', cb)
            try:
                res = self.raw(method, path, body, raw, ctype, hdr)
            finally:
                event.remove(eng, 'before_cursor_execute', cb)
            n_q = cnt[0]
        else:
            res = self.raw(method, path, body, raw, ctype, hdr)
        rec = {'name': name, 'method': method, 'path': path.replace(str(H), '<2^63>'),
               'input': ('<raw>' + raw) if raw is not None else (None if body is MISSING else sanitize(body)),
               'auth': None if not hdr else ('<bearer>' if 'Authorization' in hdr else '<outro>'),
               'resp': res, 'at_utc': fmt(at_utc), 'at_local': fmt(at_local), 'cls': cls}
        if only:
            rec['only'] = only
        if n_q is not None:
            rec['queries'] = n_q
        if write:
            rec['pre_state'] = pre
            rec['post_state'] = db_state()
        if post:
            rec['post'] = post(self)
        if pre_view is not None:
            rec['pre_view'] = pre_view
        if ORIG:
            spec = exp_o if exp_o is not None else merge(exp, o_more)
        else:
            spec = exp_r if exp_r is not None else merge(exp, r_more)
        if spec == 'medir':
            spec = None
        self._add(rec, spec)
        return res

    def fact(self, name, value, exp=MISSING, cls=None, only=None):
        if only and only != MODE:
            return value
        rec = {'name': name, 'fact': sanitize(value), 'cls': cls, 'at_utc': fmt(now_naive())}
        if only:
            rec['only'] = only
        spec = None if exp is MISSING else {'has': {'fact': exp}}
        self._add(rec, spec)
        return value


def counts_post(path=None):
    def f(c):
        out = {'counts': counts()}
        if path:
            r = c.raw('GET', path)
            out['get'] = {'status': r['status'], 'json': r.get('json')}
        return out
    return f


# ------------------------------------------------------------------ dados esperados do seed (fixture)
SEED_USERS = [(1, 'João Silva', A_EMAIL, 'admin'), (2, 'Maria Santos', M_EMAIL, 'user'), (3, 'Pedro Oliveira', P_EMAIL, 'manager')]
SEED_CATS = [(1, 'Backend', '#3498db'), (2, 'Frontend', '#2ecc71'), (3, 'DevOps', '#e74c3c'), (4, 'Bug', '#e67e22')]
# id: (título, status, prioridade, user, categoria, prazo em dias, tags)
SEED_TASKS = {
    1: ('Implementar autenticação JWT', 'pending', 1, 1, 1, -3, []),
    2: ('Criar tela de login', 'in_progress', 2, 2, 2, 5, []),
    3: ('Configurar CI/CD', 'done', 2, 3, 3, None, ['devops', 'ci', 'github']),
    4: ('Corrigir bug no filtro de busca', 'pending', 1, 1, 4, -1, []),
    5: ('Adicionar paginação na API', 'pending', 3, 1, 1, 10, []),
    6: ('Escrever testes unitários', 'pending', 2, 2, 1, None, []),
    7: ('Documentar API com Swagger', 'cancelled', 4, 3, 1, None, []),
    8: ('Refatorar models', 'in_progress', 3, 2, 1, None, ['refactor', 'tech-debt']),
    9: ('Configurar monitoramento', 'pending', 4, 3, 3, 20, []),
    10: ('Melhorar validações de input', 'pending', 3, 1, 1, None, ['improvement', 'validation']),
}
TASK_KEYS = ['id', 'title', 'description', 'status', 'priority', 'user_id', 'category_id', 'created_at',
             'updated_at', 'due_date', 'tags']
USER_KEYS = ['id', 'name', 'email', 'role', 'active', 'created_at']


def seed_task_has(prefix, tid, overdue=MISSING, names=False):
    t, st, pr, u, cat, due, tags = SEED_TASKS[tid]
    has = {f'{prefix}.id': tid, f'{prefix}.title': t, f'{prefix}.status': st, f'{prefix}.priority': pr,
           f'{prefix}.user_id': u, f'{prefix}.category_id': cat, f'{prefix}.tags': tags}
    ts = {}
    if due is None:
        has[f'{prefix}.due_date'] = None
    else:
        ts[f'{prefix}.due_date'] = [due * 86400, 300]
    ts[f'{prefix}.created_at'] = [0, 300]
    if overdue is not MISSING:
        has[f'{prefix}.overdue'] = overdue
    if names:
        has[f'{prefix}.user_name'] = SEED_USERS[u - 1][1]
        has[f'{prefix}.category_name'] = SEED_CATS[cat - 1][1]
    return has, ts


def seed_overdue(tid):
    t, st, pr, u, cat, due, tags = SEED_TASKS[tid]
    return due is not None and due < 0 and st not in ('done', 'cancelled')


# ------------------------------------------------------------------ grupos: leitura
def g_seed_leitura(c):
    c.reseed()
    from database import db
    with c.app.app_context():
        c.fact('caminho efetivo do banco', os.path.relpath(db.engine.url.database, COPY), exp='instance/tasks.db')
    c.case('GET /', 'GET', '/', exp=S(200, has={'resp.json': {'message': 'Task Manager API', 'version': '1.0'}}))
    c.case('GET /health', 'GET', '/health', exp=S(200, has={'resp.json.status': 'ok'}, keys={'resp.json': ['status', 'timestamp']},
                                                    ts={'resp.json.timestamp': ['local', 120]}))
    has, ts = {}, {}
    for i, tid in enumerate(range(1, 11)):
        h, t = seed_task_has(f'resp.json.{i}', tid, overdue=seed_overdue(tid), names=True)
        has.update(h); ts.update(t)
    c.case('GET /tasks seed', 'GET', '/tasks', qc=True, exp=S(200, ids={'resp.json': list(range(1, 11))}, has=has, ts=ts,
           keys={'resp.json.*': TASK_KEYS + ['overdue', 'user_name', 'category_name']}), r_more={'max_queries': 1})
    h, t = seed_task_has('resp.json', 1, overdue=True)
    c.case('GET /tasks/1 atrasada', 'GET', '/tasks/1', exp=S(200, has=h, ts=t, keys={'resp.json': TASK_KEYS + ['overdue']}))
    h, t = seed_task_has('resp.json', 2, overdue=False)
    c.case('GET /tasks/2 nao atrasada', 'GET', '/tasks/2', exp=S(200, has=h, ts=t))
    c.case('GET /tasks/999', 'GET', '/tasks/999', exp=S(404, 'Task não encontrada'))
    c.case('GET /tasks/abc conversor', 'GET', '/tasks/abc', exp_o=S(404, is_json=False),
           exp_r=S(404, 'Recurso não encontrado'), cls='M-03')
    searches = [('q=login', [2]), ('q=%25', list(range(1, 11))), ("q=x'%20OR%20'1'='1", []),
                ('status=pending', [1, 4, 5, 6, 9, 10]), ('status=xyz', []), ('priority=2', [2, 3, 6]),
                ('priority=%202%20', [2, 3, 6]), ('priority=%2B2', [2, 3, 6]), ('user_id=1', [1, 4, 5, 10]),
                ('q=a&status=pending&priority=1', [1, 4]), ('', list(range(1, 11))), ('priority=1&priority=2', [1, 4])]
    for qs, ids in searches:
        c.case(f'GET /tasks/search?{qs}', 'GET', f'/tasks/search?{qs}',
               exp=S(200, ids={'resp.json': ids}, keys={'resp.json.*': TASK_KEYS} if ids else {}))
    for qs, msg in [('priority=abc', 'Prioridade inválida'), ('priority=2.5', 'Prioridade inválida'),
                    ('user_id=abc', 'Usuário inválido')]:
        c.case(f'GET /tasks/search?{qs}', 'GET', f'/tasks/search?{qs}', exp_o=S(500, is_json=False),
               exp_r=REJ(400, msg, write=False), cls='C-05')
    c.case('GET /tasks/stats', 'GET', '/tasks/stats', exp=S(200, has={'resp.json': {
        'total': 10, 'pending': 6, 'in_progress': 2, 'done': 1, 'cancelled': 1, 'overdue': 2, 'completion_rate': 10.0}}))
    uhas = {}
    for i, (uid, name, email, role) in enumerate(SEED_USERS):
        uhas.update({f'resp.json.{i}.id': uid, f'resp.json.{i}.name': name, f'resp.json.{i}.email': email,
                     f'resp.json.{i}.role': role, f'resp.json.{i}.active': True,
                     f'resp.json.{i}.task_count': [4, 3, 3][i]})
    c.case('GET /users', 'GET', '/users', qc=True, exp=S(200, has=uhas, ids={'resp.json': [1, 2, 3]},
           keys={'resp.json.*': USER_KEYS + ['task_count']}, ts={'resp.json.*.created_at': [0, 300]}),
           r_more={'max_queries': 1})
    c.case('GET /users/1', 'GET', '/users/1', cls='F-01', exp=S(200, has={
        'resp.json.id': 1, 'resp.json.name': 'João Silva', 'resp.json.email': A_EMAIL, 'resp.json.role': 'admin',
        'resp.json.active': True}, ids={'resp.json.tasks': [1, 4, 5, 10]}),
        r_more={'keys': {'resp.json': USER_KEYS + ['tasks']}})
    c.case('GET /users/999', 'GET', '/users/999', exp=S(404, 'Usuário não encontrado'))
    c.case('GET /users/2/tasks', 'GET', '/users/2/tasks', exp=S(200, ids={'resp.json': [2, 6, 8]}, has={
        'resp.json.*.overdue': False, 'resp.json.0.title': 'Criar tela de login'},
        keys={'resp.json.*': ['id', 'title', 'description', 'status', 'priority', 'created_at', 'due_date', 'overdue']}))
    c.case('GET /users/999/tasks', 'GET', '/users/999/tasks', exp=S(404, 'Usuário não encontrado'))
    c.case('GET /reports/summary', 'GET', '/reports/summary', qc=True, exp=S(200, has={
        'resp.json.overview': {'total_tasks': 10, 'total_users': 3, 'total_categories': 4},
        'resp.json.tasks_by_status': {'pending': 6, 'in_progress': 2, 'done': 1, 'cancelled': 1},
        'resp.json.tasks_by_priority': {'critical': 2, 'high': 3, 'medium': 3, 'low': 2, 'minimal': 0},
        'resp.json.overdue.count': 2, 'resp.json.overdue.tasks.0.days_overdue': 3,
        'resp.json.overdue.tasks.1.days_overdue': 1,
        'resp.json.recent_activity': {'tasks_created_last_7_days': 10, 'tasks_completed_last_7_days': 1},
        'resp.json.user_productivity': [
            {'user_id': 1, 'user_name': 'João Silva', 'total_tasks': 4, 'completed_tasks': 0, 'completion_rate': 0.0},
            {'user_id': 2, 'user_name': 'Maria Santos', 'total_tasks': 3, 'completed_tasks': 0, 'completion_rate': 0.0},
            {'user_id': 3, 'user_name': 'Pedro Oliveira', 'total_tasks': 3, 'completed_tasks': 1, 'completion_rate': 33.33}]},
        ids={'resp.json.overdue.tasks': [1, 4]}, ts={'resp.json.generated_at': [0, 120],
                                                     'resp.json.overdue.tasks.0.due_date': [-3 * 86400, 300]}),
        r_more={'max_queries': 9})
    c.case('GET /reports/user/1', 'GET', '/reports/user/1', exp=S(200, has={
        'resp.json.user': {'id': 1, 'name': 'João Silva', 'email': A_EMAIL},
        'resp.json.statistics': {'total_tasks': 4, 'done': 0, 'pending': 4, 'in_progress': 0, 'cancelled': 0,
                                 'overdue': 2, 'high_priority': 2, 'completion_rate': 0.0}}))
    c.case('GET /reports/user/3', 'GET', '/reports/user/3', exp=S(200, has={
        'resp.json.statistics': {'total_tasks': 3, 'done': 1, 'pending': 1, 'in_progress': 0, 'cancelled': 1,
                                 'overdue': 0, 'high_priority': 1, 'completion_rate': 33.33}}))
    c.case('GET /reports/user/999', 'GET', '/reports/user/999', exp=S(404, 'Usuário não encontrado'))
    chas = {}
    for i, (cid, name, color) in enumerate(SEED_CATS):
        chas.update({f'resp.json.{i}.name': name, f'resp.json.{i}.color': color,
                     f'resp.json.{i}.task_count': [6, 1, 2, 1][i]})
    c.case('GET /categories', 'GET', '/categories', qc=True, exp=S(200, ids={'resp.json': [1, 2, 3, 4]}, has=chas,
           keys={'resp.json.*': ['id', 'name', 'description', 'color', 'created_at', 'task_count']}),
           r_more={'max_queries': 1})
    c.case('GET /nao-existe', 'GET', '/nao-existe', exp_o=S(404, is_json=False),
           exp_r=S(404, 'Recurso não encontrado'), cls='M-03')


def g_vazio(c):
    q('DELETE FROM tasks'); q('DELETE FROM users'); q('DELETE FROM categories')
    c.case('vazio GET /tasks', 'GET', '/tasks', qc=True, exp=S(200, has={'resp.json': []}), r_more={'max_queries': 1})
    c.case('vazio GET /tasks/stats', 'GET', '/tasks/stats', exp=S(200, has={'resp.json': {
        'total': 0, 'pending': 0, 'in_progress': 0, 'done': 0, 'cancelled': 0, 'overdue': 0, 'completion_rate': 0}}))
    c.case('vazio GET /users', 'GET', '/users', qc=True, exp=S(200, has={'resp.json': []}), r_more={'max_queries': 1})
    c.case('vazio GET /reports/summary', 'GET', '/reports/summary', qc=True, exp=S(200, has={
        'resp.json.overview': {'total_tasks': 0, 'total_users': 0, 'total_categories': 0},
        'resp.json.overdue': {'count': 0, 'tasks': []}, 'resp.json.user_productivity': [],
        'resp.json.tasks_by_priority': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'minimal': 0}}),
        r_more={'max_queries': 9})
    c.case('vazio GET /categories', 'GET', '/categories', qc=True, exp=S(200, has={'resp.json': []}), r_more={'max_queries': 1})
    c.case('vazio GET /tasks/search', 'GET', '/tasks/search', exp=S(200, has={'resp.json': []}))


def g_bordas(c):
    q('DELETE FROM tasks'); q('DELETE FROM users'); q('DELETE FROM categories')
    has_nonce = 'auth_nonce' in columns('users')
    n = now_naive()

    def ts(d):
        return fmt(n + timedelta(days=d))
    for uid, name, email, role in [(1, 'Ana', 'ana@x.com', 'admin'), (2, 'Bia', 'bia@x.com', 'user')]:
        cols = 'id,name,email,password,role,active,created_at' + (',auth_nonce' if has_nonce else '')
        vals = [uid, name, email, 'f' * 32, role, 1, ts(-1)] + ([secrets.token_urlsafe(32)] if has_nonce else [])
        q(f'INSERT INTO users ({cols}) VALUES ({",".join("?" * len(vals))})', vals)
    q("INSERT INTO categories (id,name,description,color,created_at) VALUES (1,'Cat A','d','#111111',?)", (ts(-1),))
    q("INSERT INTO categories (id,name,description,color,created_at) VALUES (2,'Cat Vazia','d','#222222',?)", (ts(-1),))
    rows = [(1, 'Pendente atrasada', 'pending', 1, 1, 1, -3, -1, -1, None),
            (2, 'Em progresso atrasada', 'in_progress', 2, 1, 1, -1, -1, -1, 'a,b'),
            (3, 'Concluida atrasada', 'done', 5, 1, 1, -3, -10, -6, None),
            (4, 'Cancelada atrasada', 'cancelled', 4, 1, None, -3, -1, -1, None),
            (5, 'Sem vinculos', 'pending', 3, None, None, None, -8, -8, None),
            (6, 'Concluida antiga', 'done', 2, 1, 1, None, -8, -8, None),
            (7, 'Futura', 'pending', 3, None, 1, 5, -6, -6, None)]
    for tid, title, st, pr, uid, cid, due, cr, up, tags in rows:
        q('INSERT INTO tasks (id,title,description,status,priority,user_id,category_id,created_at,updated_at,due_date,tags) '
          'VALUES (?,?,?,?,?,?,?,?,?,?,?)', (tid, title, 'desc', st, pr, uid, cid, ts(cr), ts(up),
                                              ts(due) if due is not None else None, tags))
    overdue = [True, True, False, False, False, False, False]
    has = {f'resp.json.{i}.overdue': o for i, o in enumerate(overdue)}
    has.update({'resp.json.4.user_name': None, 'resp.json.4.category_name': None, 'resp.json.6.user_name': None,
                'resp.json.6.category_name': 'Cat A', 'resp.json.3.category_name': None, 'resp.json.1.tags': ['a', 'b'],
                'resp.json.0.user_name': 'Ana'})
    c.case('bordas GET /tasks', 'GET', '/tasks', qc=True, exp=S(200, ids={'resp.json': [1, 2, 3, 4, 5, 6, 7]}, has=has,
           ts={'resp.json.2.created_at': [-10 * 86400, 120], 'resp.json.2.updated_at': [-6 * 86400, 120]}),
           r_more={'max_queries': 1})
    c.case('bordas GET /tasks/1', 'GET', '/tasks/1', exp=S(200, has={'resp.json.overdue': True}))
    c.case('bordas GET /tasks/3 done atrasada', 'GET', '/tasks/3', exp=S(200, has={'resp.json.overdue': False}))
    c.case('bordas GET /tasks/stats', 'GET', '/tasks/stats', exp=S(200, has={'resp.json': {
        'total': 7, 'pending': 3, 'in_progress': 1, 'done': 2, 'cancelled': 1, 'overdue': 2, 'completion_rate': 28.57}}))
    c.case('bordas GET /users', 'GET', '/users', qc=True, exp=S(200, has={
        'resp.json.0.task_count': 5, 'resp.json.1.task_count': 0}, ids={'resp.json': [1, 2]}), r_more={'max_queries': 1})
    c.case('bordas GET /users/2/tasks', 'GET', '/users/2/tasks', exp=S(200, has={'resp.json': []}))
    c.case('bordas GET /users/1/tasks', 'GET', '/users/1/tasks', exp=S(200, ids={'resp.json': [1, 2, 3, 4, 6]},
           has={'resp.json.0.overdue': True, 'resp.json.1.overdue': True, 'resp.json.2.overdue': False}))
    c.case('bordas GET /reports/summary', 'GET', '/reports/summary', qc=True, exp=S(200, has={
        'resp.json.recent_activity': {'tasks_created_last_7_days': 4, 'tasks_completed_last_7_days': 1},
        'resp.json.overdue.count': 2, 'resp.json.overdue.tasks.0.days_overdue': 3, 'resp.json.overdue.tasks.1.days_overdue': 1,
        'resp.json.tasks_by_priority': {'critical': 1, 'high': 2, 'medium': 2, 'low': 1, 'minimal': 1},
        'resp.json.user_productivity': [
            {'user_id': 1, 'user_name': 'Ana', 'total_tasks': 5, 'completed_tasks': 2, 'completion_rate': 40.0},
            {'user_id': 2, 'user_name': 'Bia', 'total_tasks': 0, 'completed_tasks': 0, 'completion_rate': 0}]}),
        r_more={'max_queries': 9})
    c.case('bordas GET /reports/user/1', 'GET', '/reports/user/1', exp=S(200, has={'resp.json.statistics': {
        'total_tasks': 5, 'done': 2, 'pending': 1, 'in_progress': 1, 'cancelled': 1, 'overdue': 2, 'high_priority': 3,
        'completion_rate': 40.0}}))
    c.case('bordas GET /reports/user/2', 'GET', '/reports/user/2', exp=S(200, has={'resp.json.statistics': {
        'total_tasks': 0, 'done': 0, 'pending': 0, 'in_progress': 0, 'cancelled': 0, 'overdue': 0, 'high_priority': 0,
        'completion_rate': 0}}))
    c.case('bordas GET /categories', 'GET', '/categories', qc=True, exp=S(200, has={
        'resp.json.0.task_count': 5, 'resp.json.1.task_count': 0}), r_more={'max_queries': 1})
    c.case('bordas GET /tasks/search?user_id=1', 'GET', '/tasks/search?user_id=1', exp=S(200, ids={'resp.json': [1, 2, 3, 4, 6]}))


# ------------------------------------------------------------------ grupos: escrita de tasks
def _task_created(has_extra=None, ts_extra=None):
    has = {'resp.json.id': 11, 'post.counts.tasks': 11, 'post.get.json.id': 11}
    has.update(has_extra or {})
    for k, v in list((has_extra or {}).items()):
        if k.startswith('resp.json.'):
            has['post.get.json.' + k[len('resp.json.'):]] = v
    ts = {'resp.json.created_at': [0, 120], 'resp.json.updated_at': [0, 120]}
    ts.update(ts_extra or {})
    return S(201, None, has=has, ts=ts, changed=True, keys={'resp.json': TASK_KEYS})


def g_tasks_escrita(c):
    t = 'Título válido'
    created = _task_created
    P = [
        ('minimo', {'title': 'Nova task'}, created({'resp.json.title': 'Nova task', 'resp.json.status': 'pending',
         'resp.json.priority': 3, 'resp.json.description': '', 'resp.json.tags': [], 'resp.json.user_id': None,
         'resp.json.category_id': None, 'resp.json.due_date': None}), None, None),
        ('completo', {'title': 'Completa', 'description': 'd', 'status': 'in_progress', 'priority': 2, 'user_id': 1,
                      'category_id': 1, 'due_date': '2030-01-15', 'tags': ['a', 'b']},
         created({'resp.json.title': 'Completa', 'resp.json.description': 'd', 'resp.json.status': 'in_progress',
                  'resp.json.priority': 2, 'resp.json.user_id': 1, 'resp.json.category_id': 1,
                  'resp.json.due_date': '2030-01-15 00:00:00', 'resp.json.tags': ['a', 'b']}), None, None),
        ('title 200', {'title': 'y' * 200}, created({'resp.json.title': 'y' * 200}), None, None),
        ('description null', {'title': t, 'description': None}, created({'resp.json.description': None}), None, None),
        ('priority 2.0', {'title': t, 'priority': 2.0}, created({'resp.json.priority': 2}), None, None),
        ('due_date sem zero', {'title': t, 'due_date': '2030-1-5'}, created({'resp.json.due_date': '2030-01-05 00:00:00'}), None, None),
        ('due_date ""', {'title': t, 'due_date': ''}, created({'resp.json.due_date': None}), None, None),
        ('tags elemento vazio', {'title': t, 'tags': ['', 'x']}, created({'resp.json.tags': ['', 'x']}), None, None),
        ('tags string', {'title': t, 'tags': 'a,b'}, created({'resp.json.tags': ['a', 'b']}), None, None),
        ('tags 0 (POST: falso = sem tags)', {'title': t, 'tags': 0}, created({'resp.json.tags': []}), None, None),
        ('campos extras', {'title': t, 'id': 77, 'created_at': 'x', 'auth_nonce': 'y'}, created({'resp.json.title': t}), None, None),
    ]
    rej = [  # (nome, corpo, exp_o, exp_r(status,msg), cls)
        ('corpo null', None, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo {}', {}, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo []', [], S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo ""', '', S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo 0', 0, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo false', False, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo "x"', 'x', S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo true', True, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('title ausente', {'priority': 2}, S(400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title null', {'title': None}, S(400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title ""', {'title': ''}, S(400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title curto', {'title': 'ab'}, S(400, 'Título muito curto'), (400, 'Título muito curto'), None),
        ('title longo', {'title': 'x' * 201}, S(400, 'Título muito longo'), (400, 'Título muito longo'), None),
        ('title numero', {'title': 5}, S(500, is_json=False), (400, 'Título inválido'), 'C-02'),
        ('title true', {'title': True}, S(500, is_json=False), (400, 'Título inválido'), 'C-02'),
        ('title lista 2', {'title': ['a', 'b']}, S(400, 'Título muito curto'), (400, 'Título inválido'), 'C-02'),
        ('title lista 3', {'title': ['a', 'b', 'c']}, S(500, 'Erro ao criar task'), (400, 'Título inválido'), 'C-02'),
        ('description numero', {'title': t, 'description': 5}, S(201), (400, 'Descrição inválida'), 'R-02'),
        ('description true', {'title': t, 'description': True}, S(201), (400, 'Descrição inválida'), 'R-02'),
        ('description lista', {'title': t, 'description': ['x']}, S(500, 'Erro ao criar task'), (400, 'Descrição inválida'), 'C-10'),
        ('description objeto', {'title': t, 'description': {'a': 1}}, S(500, 'Erro ao criar task'), (400, 'Descrição inválida'), 'C-10'),
        ('status invalido', {'title': t, 'status': 'xyz'}, S(400, 'Status inválido'), (400, 'Status inválido'), None),
        ('status null', {'title': t, 'status': None}, S(400, 'Status inválido'), (400, 'Status inválido'), None),
        ('status numero', {'title': t, 'status': 5}, S(400, 'Status inválido'), (400, 'Status inválido'), None),
        ('priority false', {'title': t, 'priority': False}, S(400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade inválida'), 'M-04'),
        ('priority true', {'title': t, 'priority': True}, S(201), (400, 'Prioridade inválida'), 'R-03'),
        ('priority 2.5', {'title': t, 'priority': 2.5}, S(201), (400, 'Prioridade inválida'), 'R-03'),
        ('priority 0', {'title': t, 'priority': 0}, S(400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('priority 6', {'title': t, 'priority': 6}, S(400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('priority 2^63', {'title': t, 'priority': H}, S(400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('priority "2"', {'title': t, 'priority': '2'}, S(500, is_json=False), (400, 'Prioridade inválida'), 'C-03'),
        ('priority null', {'title': t, 'priority': None}, S(500, is_json=False), (400, 'Prioridade inválida'), 'C-03'),
        ('priority lista', {'title': t, 'priority': [1]}, S(500, is_json=False), (400, 'Prioridade inválida'), 'C-03'),
        ('user_id 999', {'title': t, 'user_id': 999}, S(404, 'Usuário não encontrado'), (404, 'Usuário não encontrado'), None),
        ('user_id 2^63', {'title': t, 'user_id': H}, 'medir', (404, 'Usuário não encontrado'), 'C-12'),
        ('user_id 0', {'title': t, 'user_id': 0}, S(201), (400, 'Usuário inválido'), 'R-04'),
        ('user_id false', {'title': t, 'user_id': False}, S(201), (400, 'Usuário inválido'), 'R-04'),
        ('user_id ""', {'title': t, 'user_id': ''}, S(201), (400, 'Usuário inválido'), 'R-04'),
        ('user_id "1"', {'title': t, 'user_id': '1'}, S(201), (400, 'Usuário inválido'), 'R-04'),
        ('user_id true', {'title': t, 'user_id': True}, S(201), (400, 'Usuário inválido'), 'R-04'),
        ('user_id -1', {'title': t, 'user_id': -1}, S(404, 'Usuário não encontrado'), (400, 'Usuário inválido'), 'M-02'),
        ('user_id 1.5', {'title': t, 'user_id': 1.5}, S(404, 'Usuário não encontrado'), (400, 'Usuário inválido'), 'M-02'),
        ('user_id "abc"', {'title': t, 'user_id': 'abc'}, S(404, 'Usuário não encontrado'), (400, 'Usuário inválido'), 'M-02'),
        ('user_id lista', {'title': t, 'user_id': [1]}, S(500, 'Erro ao criar task'), (400, 'Usuário inválido'), 'C-11'),
        ('user_id objeto', {'title': t, 'user_id': {'id': 1}}, S(500, 'Erro ao criar task'), (400, 'Usuário inválido'), 'C-11'),
        ('category_id 999', {'title': t, 'category_id': 999}, S(404, 'Categoria não encontrada'), (404, 'Categoria não encontrada'), None),
        ('category_id 2^63', {'title': t, 'category_id': H}, 'medir', (404, 'Categoria não encontrada'), 'C-12'),
        ('category_id 0', {'title': t, 'category_id': 0}, S(201), (400, 'Categoria inválida'), 'R-04'),
        ('category_id "1"', {'title': t, 'category_id': '1'}, S(201), (400, 'Categoria inválida'), 'R-04'),
        ('category_id -1', {'title': t, 'category_id': -1}, S(404, 'Categoria não encontrada'), (400, 'Categoria inválida'), 'M-02'),
        ('due_date invalida', {'title': t, 'due_date': '2030-13-01'}, S(400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('due_date numero', {'title': t, 'due_date': 5}, S(400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('due_date dd/mm', {'title': t, 'due_date': '15/01/2030'}, S(400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('tags elemento numero', {'title': t, 'tags': [1]}, S(500, is_json=False), (400, 'Tags inválidas'), 'C-04'),
        ('tags com virgula', {'title': t, 'tags': ['a,b']}, S(201), (400, 'Tags inválidas'), 'R-05'),
        ('tags numero', {'title': t, 'tags': 5}, S(201), (400, 'Tags inválidas'), 'R-05'),
        ('tags true', {'title': t, 'tags': True}, S(201), (400, 'Tags inválidas'), 'R-05'),
        ('tags objeto', {'title': t, 'tags': {'a': 1}}, S(500, 'Erro ao criar task'), (400, 'Tags inválidas'), 'C-04'),
    ]
    for name, body, er, eo, cls in P:
        c.case(f'POST /tasks {name}', 'POST', '/tasks', body=body, exp=er, reseed=True, post=counts_post('/tasks/11'))
    for name, body, eo, (st, msg), cls in rej:
        c.case(f'POST /tasks {name}', 'POST', '/tasks', body=body, exp_o=eo, exp_r=REJ(st, msg), cls=cls,
               reseed=True, post=counts_post('/tasks/11'))
    c.case('POST /tasks priority NaN', 'POST', '/tasks', raw='{"title": "Título válido", "priority": NaN}',
           exp_o=S(201), exp_r=REJ(400, 'Prioridade inválida'), cls='R-03', reseed=True, post=counts_post('/tasks/11'))
    for sign in ('', '-'):
        c.case(f'POST /tasks priority {sign}Infinity', 'POST', '/tasks',
               raw='{"title": "Título válido", "priority": %sInfinity}' % sign,
               exp_o=S(400, 'Prioridade deve ser entre 1 e 5'), exp_r=REJ(400, 'Prioridade inválida'), cls='M-01',
               reseed=True, post=counts_post())
    c.case('POST /tasks ctype texto', 'POST', '/tasks', raw='abc', ctype='text/plain', exp_o=S(415, is_json=False),
           exp_r=REJ(415, 'Dados inválidos'), cls='C-JSON', reseed=True, post=counts_post())
    c.case('POST /tasks json malformado', 'POST', '/tasks', raw='{"title": ', exp_o=S(400, is_json=False),
           exp_r=REJ(400, 'Dados inválidos'), cls='C-JSON', reseed=True, post=counts_post())

    orig_title = SEED_TASKS[1][0]

    def upd(has_extra):
        has = dict(has_extra)
        for k, v in has_extra.items():
            has['post.get.json.' + k[len('resp.json.'):]] = v
        has['resp.json.id'] = 1
        return S(200, None, has=has, ts={'resp.json.updated_at': [0, 120]}, changed=True, keys={'resp.json': TASK_KEYS})
    U = [
        ('title', {'title': 'Novo título'}, upd({'resp.json.title': 'Novo título'})),
        ('description', {'description': 'nd'}, upd({'resp.json.description': 'nd'})),
        ('status', {'status': 'done'}, upd({'resp.json.status': 'done'})),
        ('priority 5', {'priority': 5}, upd({'resp.json.priority': 5})),
        ('desvincula user', {'user_id': None}, upd({'resp.json.user_id': None})),
        ('desvincula category', {'category_id': None}, upd({'resp.json.category_id': None})),
        ('user 2', {'user_id': 2}, upd({'resp.json.user_id': 2})),
        ('due null', {'due_date': None}, upd({'resp.json.due_date': None})),
        ('due valida', {'due_date': '2031-02-03'}, upd({'resp.json.due_date': '2031-02-03 00:00:00'})),
        ('tags lista', {'tags': ['p', 'q']}, upd({'resp.json.tags': ['p', 'q']})),
        ('tags null limpa', {'tags': None}, upd({'resp.json.tags': []})),
        ('tags "" limpa', {'tags': ''}, upd({'resp.json.tags': []})),
        ('tags [] limpa', {'tags': []}, upd({'resp.json.tags': []})),
    ]
    for name, body, spec in U:
        c.case(f'PUT /tasks/1 {name}', 'PUT', '/tasks/1', body=body, exp=spec, reseed=True,
               setup=(lambda cc: q("UPDATE tasks SET tags='x,y' WHERE id=1")) if name.startswith('tags') else None,
               post=counts_post('/tasks/1'))
    UR = [
        ('user 999', {'user_id': 999}, S(404, 'Usuário não encontrado'), (404, 'Usuário não encontrado'), None),
        ('user 2^63', {'user_id': H}, 'medir', (404, 'Usuário não encontrado'), 'C-12'),
        ('due invalida', {'due_date': 'bad'}, S(400, 'Formato de data inválido'), (400, 'Formato de data inválido'), None),
        ('combinado titulo+prioridade invalida', {'title': 'Título Combinado', 'priority': 9},
         S(400, 'Prioridade deve ser entre 1 e 5', has={'post.get.json.title': orig_title}),
         (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('corpo {}', {}, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo null', None, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo "x"', 'x', S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo 5', 5, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo true', True, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo "title"', 'title', S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('title null', {'title': None}, S(500, is_json=False), (400, 'Título inválido'), 'C-02'),
        ('title numero', {'title': 5}, S(500, is_json=False), (400, 'Título inválido'), 'C-02'),
        ('title false', {'title': False}, S(500, is_json=False), (400, 'Título inválido'), 'C-02'),
        ('title ""', {'title': ''}, S(400, 'Título muito curto'), (400, 'Título muito curto'), None),
        ('priority false', {'priority': False}, S(400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade inválida'), 'M-04'),
        ('priority true', {'priority': True}, S(200), (400, 'Prioridade inválida'), 'R-03'),
        ('priority "2"', {'priority': '2'}, S(500, is_json=False), (400, 'Prioridade inválida'), 'C-03'),
        ('priority 2.5', {'priority': 2.5}, S(200), (400, 'Prioridade inválida'), 'R-03'),
        ('user_id 0', {'user_id': 0}, S(200), (400, 'Usuário inválido'), 'R-04'),
        ('description numero', {'description': 5}, S(200), (400, 'Descrição inválida'), 'R-02'),
        ('tags 0', {'tags': 0}, S(200, has={'post.get.json.tags': ['0']}), (400, 'Tags inválidas'), 'R-05'),
        ('tags false', {'tags': False}, S(200, has={'post.get.json.tags': ['0']}), (400, 'Tags inválidas'), 'R-05'),
        ('tags 0.0', {'tags': 0.0}, 'medir', (400, 'Tags inválidas'), 'R-05'),
        ('tags {}', {'tags': {}}, 'medir', (400, 'Tags inválidas'), 'C-04'),
    ]
    for name, body, eo, (st, msg), cls in UR:
        er = REJ(st, msg)
        if name.startswith('combinado'):
            er['has'] = {'post.get.json.title': orig_title}
        if name.startswith('tags'):
            er['has'] = {'post.get.json.tags': ['x', 'y']}
        c.case(f'PUT /tasks/1 {name}', 'PUT', '/tasks/1', body=body, exp_o=eo, exp_r=er, cls=cls, reseed=True,
               setup=(lambda cc: q("UPDATE tasks SET tags='x,y' WHERE id=1")) if name.startswith('tags') else None,
               post=counts_post('/tasks/1'))
    c.case('PUT /tasks/999', 'PUT', '/tasks/999', body={'title': 'abc'}, exp=REJ(404, 'Task não encontrada'), reseed=True)
    c.case('DELETE /tasks/1', 'DELETE', '/tasks/1', reseed=True, post=counts_post('/tasks/1'),
           exp=S(200, has={'resp.json': {'message': 'Task deletada com sucesso'}, 'post.counts.tasks': 9,
                           'post.get.status': 404}, changed=True))
    c.case('DELETE /tasks/1 repetido', 'DELETE', '/tasks/1', exp=REJ(404, 'Task não encontrada'))
    c.case('GET /tasks/stats apos criar e concluir', 'GET', '/tasks/stats', reseed=True,
           setup=lambda cc: (cc.raw('POST', '/tasks', {'title': 'Para concluir'}), cc.raw('PUT', '/tasks/11', {'status': 'done'})),
           exp=S(200, has={'resp.json': {'total': 11, 'pending': 6, 'in_progress': 2, 'done': 2, 'cancelled': 1,
                                         'overdue': 2, 'completion_rate': 18.18}}))


# ------------------------------------------------------------------ grupos: usuários
def g_users_escrita(c):
    ok = {'name': 'Novo', 'email': 'novo@email.com', 'password': PW['cadastro']}

    def created(role='user'):
        return S(201, None, has={'resp.json.id': 4, 'resp.json.name': 'Novo', 'resp.json.email': 'novo@email.com',
                                 'resp.json.role': role, 'resp.json.active': True, 'post.counts.users': 4,
                                 'post.login_cadastro': 200},
                 ts={'resp.json.created_at': [0, 120]}, changed=True)

    def post(cc):
        out = counts_post()(cc)
        out['hash_novo'] = hash_kind('novo@email.com')
        out['login_cadastro'] = cc.client.post('/login', json={'email': 'novo@email.com', 'password': PW['cadastro']}).status_code \
            if out['hash_novo'] else None
        return out
    PS = [('sucesso', ok, None, created(), None, None),
          ('role admin com admin', {**ok, 'role': 'admin'}, 'A', created('admin'), None, None),
          ('role user com user', {**ok, 'role': 'user'}, 'M', created('user'), None, None),
          ('active ignorado', {**ok, 'active': False}, None, created(), None, None)]
    for name, body, hdr, spec, _, cls in PS:
        c.case(f'POST /users {name}', 'POST', '/users', body=body, hdr=hdr, reseed=True, post=post, exp=spec,
               r_more={'has': {'post.hash_novo': 'werkzeug-scrypt'}, 'keys': {'resp.json': USER_KEYS}},
               o_more={'has': {'post.hash_novo': 'md5'}}, cls='F-01')
    PR = [
        ('duplicado', {**ok, 'email': A_EMAIL}, None, S(409, 'Email já cadastrado'), (409, 'Email já cadastrado'), None),
        ('sem name', {'email': 'a@b.com', 'password': PW['cadastro']}, None, S(400, 'Nome é obrigatório'), (400, 'Nome é obrigatório'), None),
        ('sem email', {'name': 'A', 'password': PW['cadastro']}, None, S(400, 'Email é obrigatório'), (400, 'Email é obrigatório'), None),
        ('sem password', {'name': 'A', 'email': 'a@b.com'}, None, S(400, 'Senha é obrigatória'), (400, 'Senha é obrigatória'), None),
        ('name numero', {**ok, 'name': 5}, None, S(201), (400, 'Nome inválido'), 'R-06'),
        ('name lista', {**ok, 'name': ['a']}, None, S(500, 'Erro ao criar usuário'), (400, 'Nome inválido'), 'C-10'),
        ('email numero', {**ok, 'email': 5}, None, S(500, is_json=False), (400, 'Email inválido'), 'C-06'),
        ('email invalido', {**ok, 'email': 'bad'}, None, S(400, 'Email inválido'), (400, 'Email inválido'), None),
        ('password numero', {**ok, 'password': 12345678}, None, S(500, is_json=False), (400, 'Senha inválida'), 'C-06'),
        ('password curta', {**ok, 'password': 'abc'}, None, S(400, 'Senha deve ter no mínimo 4 caracteres'), (400, 'Senha deve ter no mínimo 4 caracteres'), None),
        ('password lista', {**ok, 'password': ['a', 'b', 'c', 'd']}, None, S(500, is_json=False), (400, 'Senha inválida'), 'C-06'),
        ('role invalido', {**ok, 'role': 'xyz'}, None, S(400, 'Role inválido'), (400, 'Role inválido'), None),
        ('role null', {**ok, 'role': None}, None, S(400, 'Role inválido'), (400, 'Role inválido'), None),
        ('role admin anonimo', {**ok, 'role': 'admin'}, None, S(201), (401, 'Token ausente'), 'D-1a'),
        ('role manager com user', {**ok, 'role': 'manager'}, 'M', S(201), (403, 'Permissão negada'), 'D-1a'),
        ('bearer invalido em cadastro anonimo', ok, {'Authorization': 'Bearer xxx'}, S(201), (401, 'Token inválido'), 'D-1a'),
        ('corpo null', None, None, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], None, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, None, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, hdr, eo, (st, msg), cls in PR:
        er = REJ(st, msg, has={'post.counts.users': 3})
        c.case(f'POST /users {name}', 'POST', '/users', body=body, hdr=hdr, exp_o=eo, exp_r=er, cls=cls,
               reseed=True, post=post)

    def upd(field, value):
        return S(200, None, has={f'resp.json.{field}': value, f'post.get.json.{field}': value, 'resp.json.id': 2},
                 changed=True)
    UO = [('name', {'name': 'Maria Nova'}, upd('name', 'Maria Nova')),
          ('email', {'email': 'maria2@email.com'}, upd('email', 'maria2@email.com')),
          ('role manager', {'role': 'manager'}, upd('role', 'manager')),
          ('active false', {'active': False}, upd('active', False))]
    for name, body, spec in UO:
        c.case(f'PUT /users/2 {name} (admin)', 'PUT', '/users/2', body=body, hdr='A', exp=spec, reseed=True,
               post=counts_post('/users/2'), r_more={'keys': {'resp.json': USER_KEYS}})

    def pw_post(cc):
        out = counts_post()(cc)
        out['login_nova'] = cc.client.post('/login', json={'email': M_EMAIL, 'password': PW['nova']}).status_code
        out['login_antiga'] = cc.client.post('/login', json={'email': M_EMAIL, 'password': CRED[M_EMAIL]}).status_code
        return out
    c.case('PUT /users/2 password (admin)', 'PUT', '/users/2', body={'password': PW['nova']}, hdr='A', reseed=True,
           post=pw_post, exp=S(200, has={'post.login_nova': 200, 'post.login_antiga': 401}, changed=True))
    UR = [
        ('email duplicado', {'email': A_EMAIL}, S(409, 'Email já cadastrado'), (409, 'Email já cadastrado'), None),
        ('email invalido', {'email': 'bad'}, S(400, 'Email inválido'), (400, 'Email inválido'), None),
        ('email numero', {'email': 5}, S(500, is_json=False), (400, 'Email inválido'), 'C-06'),
        ('email null', {'email': None}, S(500, is_json=False), (400, 'Email inválido'), 'C-06'),
        ('password curta', {'password': 'abc'}, S(400, 'Senha muito curta'), (400, 'Senha muito curta'), None),
        ('password null', {'password': None}, S(500, is_json=False), (400, 'Senha inválida'), 'C-06'),
        ('password numero', {'password': 12345678}, S(500, is_json=False), (400, 'Senha inválida'), 'C-06'),
        ('role invalido', {'role': 'xyz'}, S(400, 'Role inválido'), (400, 'Role inválido'), None),
        ('active 0', {'active': 0}, S(200), (400, 'Campo active inválido'), 'R-07'),
        ('active "x"', {'active': 'x'}, S(500, 'Erro ao atualizar'), (400, 'Campo active inválido'), 'C-06'),
        ('active null', {'active': None}, S(200), (400, 'Campo active inválido'), 'R-07'),
        ('name null', {'name': None}, S(500, 'Erro ao atualizar'), (400, 'Nome inválido'), 'C-06'),
        ('name ""', {'name': ''}, S(200), (400, 'Nome inválido'), 'R-06'),
        ('name numero', {'name': 5}, S(200), (400, 'Nome inválido'), 'R-06'),
        ('corpo {}', {}, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo 5', 5, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo "name"', 'name', S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, (st, msg), cls in UR:
        c.case(f'PUT /users/2 {name} (admin)', 'PUT', '/users/2', body=body, hdr='A', exp_o=eo,
               exp_r=REJ(st, msg, has={'post.get.json.name': 'Maria Santos', 'post.get.json.email': M_EMAIL}),
               cls=cls, reseed=True, post=counts_post('/users/2'))
    c.case('PUT /users/999 (admin)', 'PUT', '/users/999', body={'name': 'x'}, hdr='A', exp=REJ(404, 'Usuário não encontrado'), reseed=True)
    c.case('DELETE /users/3 com 3 tasks (admin)', 'DELETE', '/users/3', hdr='A', reseed=True,
           post=lambda cc: {'counts': counts(), 'tasks_user3': q('SELECT COUNT(*) FROM tasks WHERE user_id=3')[0][0],
                            'tasks_outros': q('SELECT COUNT(*) FROM tasks WHERE user_id IN (1,2)')[0][0]},
           exp=S(200, has={'resp.json': {'message': 'Usuário deletado com sucesso'}, 'post.counts.users': 2,
                           'post.counts.tasks': 7, 'post.tasks_user3': 0, 'post.tasks_outros': 7}, changed=True))
    c.case('DELETE /users/4 sem tasks (admin)', 'DELETE', '/users/4', hdr='A', reseed=True,
           setup=lambda cc: cc.raw('POST', '/users', {'name': 'Sem Tasks', 'email': 'st@email.com', 'password': PW['outra']}),
           post=counts_post(), exp=S(200, has={'post.counts.users': 3, 'post.counts.tasks': 10}, changed=True))
    c.case('DELETE /users/999 (admin)', 'DELETE', '/users/999', hdr='A', exp=REJ(404, 'Usuário não encontrado'), reseed=True)
    login_ok_o = S(200, has={'resp.json.message': 'Login realizado com sucesso', 'resp.json.user.id': 1,
                             'resp.json.user.email': A_EMAIL, 'resp.json.token': '<fake-token>'})
    login_ok_r = merge(login_ok_o, {'has': {'resp.json.token': '<token>'}, 'keys': {'resp.json.user': USER_KEYS}})
    c.case('POST /login correto', 'POST', '/login', body={'email': A_EMAIL, 'password': CRED[A_EMAIL]},
           exp_o=login_ok_o, exp_r=login_ok_r, cls='D-1a', reseed=True)
    L = [
        ('senha errada', {'email': A_EMAIL, 'password': PW['errada']}, S(401, 'Credenciais inválidas'), S(401, 'Credenciais inválidas'), None),
        ('email inexistente', {'email': 'x@email.com', 'password': PW['errada']}, S(401, 'Credenciais inválidas'), S(401, 'Credenciais inválidas'), None),
        ('campos ausentes', {}, S(400, 'Dados inválidos'), S(400, 'Dados inválidos'), None),
        ('sem senha', {'email': A_EMAIL}, S(400, 'Email e senha são obrigatórios'), S(400, 'Email e senha são obrigatórios'), None),
        ('email numero', {'email': 5, 'password': PW['errada']}, S(401, 'Credenciais inválidas'), S(401, 'Credenciais inválidas', max_queries=0), 'M-05'),
        ('email true', {'email': True, 'password': PW['errada']}, S(401, 'Credenciais inválidas'), S(401, 'Credenciais inválidas', max_queries=0), 'M-05'),
        ('email lista', {'email': [A_EMAIL], 'password': PW['errada']}, S(500, is_json=False), S(401, 'Credenciais inválidas', max_queries=0), 'C-08'),
        ('email objeto', {'email': {'a': 1}, 'password': PW['errada']}, S(500, is_json=False), S(401, 'Credenciais inválidas', max_queries=0), 'C-08'),
        ('senha numero email existente', {'email': A_EMAIL, 'password': 12345678}, S(500, is_json=False), S(401, 'Credenciais inválidas'), 'C-08'),
        ('senha numero email inexistente', {'email': 'x@email.com', 'password': 12345678}, S(401, 'Credenciais inválidas'), S(401, 'Credenciais inválidas'), None),
        ('corpo null', None, S(400, 'Dados inválidos'), S(400, 'Dados inválidos'), None),
        ('corpo [1]', [1], S(500, is_json=False), S(400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, S(500, is_json=False), S(400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, er, cls in L:
        c.case(f'POST /login {name}', 'POST', '/login', body=body, exp_o=eo, exp_r=merge(er, {'unchanged': True}),
               cls=cls, reseed=True, qc=name.startswith('email '))
    c.case('POST /login inativo', 'POST', '/login', body={'email': P_EMAIL, 'password': CRED[P_EMAIL]},
           exp=S(403, 'Usuário inativo'), reseed=True, setup=lambda cc: q(f"UPDATE users SET active=0 WHERE email='{P_EMAIL}'"))


# ------------------------------------------------------------------ grupos: categorias
def g_categories_escrita(c):
    def created(has):
        h = {'resp.json.id': 5, 'post.counts.categories': 5}
        h.update(has)
        return S(201, None, has=h, ts={'resp.json.created_at': [0, 120]}, changed=True,
                 keys={'resp.json': ['id', 'name', 'description', 'color', 'created_at']})
    for name, body, spec in [
        ('padrao', {'name': 'Nova'}, created({'resp.json.name': 'Nova', 'resp.json.color': '#000000', 'resp.json.description': ''})),
        ('cor valida', {'name': 'Nova', 'color': '#ABCDEF'}, created({'resp.json.color': '#ABCDEF'})),
        ('descricao null', {'name': 'Nova', 'description': None}, created({'resp.json.description': None}))]:
        c.case(f'POST /categories {name}', 'POST', '/categories', body=body, exp=spec, reseed=True, post=counts_post())
    PR = [
        ('cor invalida', {'name': 'Nova', 'color': 'red'}, S(201), (400, 'Cor inválida'), 'R-09'),
        ('cor null', {'name': 'Nova', 'color': None}, S(201), (400, 'Cor inválida'), 'R-09'),
        ('cor com \\n final', {'name': 'Nova', 'color': '#123456\n'}, S(201), (400, 'Cor inválida'), 'R-09'),
        ('sem nome', {'color': '#ABCDEF'}, S(400, 'Nome é obrigatório'), (400, 'Nome é obrigatório'), None),
        ('nome numero', {'name': 5}, S(201), (400, 'Nome inválido'), 'R-08'),
        ('nome lista', {'name': ['a']}, S(500, 'Erro ao criar categoria'), (400, 'Nome inválido'), 'C-10'),
        ('descricao numero', {'name': 'Nova', 'description': 5}, S(201), (400, 'Descrição inválida'), 'R-08'),
        ('corpo null', None, S(400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, (st, msg), cls in PR:
        c.case(f'POST /categories {name}', 'POST', '/categories', body=body, exp_o=eo,
               exp_r=REJ(st, msg, has={'post.counts.categories': 4}), cls=cls, reseed=True, post=counts_post())

    def upd(has):
        h = {'resp.json.id': 1}
        h.update(has)
        return S(200, None, has=h, changed=True)
    c.case('PUT /categories/1 parcial', 'PUT', '/categories/1', body={'name': 'Ren'}, reseed=True, post=counts_post('/categories'),
           exp=upd({'resp.json.name': 'Ren', 'post.get.json.0.name': 'Ren', 'resp.json.color': '#3498db'}))
    c.case('PUT /categories/1 cor valida', 'PUT', '/categories/1', body={'color': '#123456'}, reseed=True,
           post=counts_post('/categories'), exp=upd({'resp.json.color': '#123456', 'post.get.json.0.color': '#123456'}))
    c.case('PUT /categories/1 corpo {}', 'PUT', '/categories/1', body={}, reseed=True, post=counts_post('/categories'),
           exp=S(200, has={'resp.json.name': 'Backend', 'resp.json.color': '#3498db'}, unchanged=True))
    UR = [
        ('corpo null', None, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo 0', 0, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo false', False, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, S(500, is_json=False), (400, 'Dados inválidos'), 'C-01'),
        ('corpo []', [], S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo ""', '', S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo [1]', [1], S(200), (400, 'Dados inválidos'), 'R-01'),
        ('corpo "x"', 'x', S(200), (400, 'Dados inválidos'), 'R-01'),
        ('nome null', {'name': None}, S(500, 'Erro ao atualizar'), (400, 'Nome é obrigatório'), 'C-09'),
        ('nome ""', {'name': ''}, S(200), (400, 'Nome inválido'), 'R-08'),
        ('nome numero', {'name': 5}, S(200), (400, 'Nome inválido'), 'R-08'),
        ('cor invalida', {'color': 'bad'}, S(200), (400, 'Cor inválida'), 'R-09'),
        ('cor com \\n final', {'color': '#123456\n'}, S(200), (400, 'Cor inválida'), 'R-09'),
    ]
    for name, body, eo, (st, msg), cls in UR:
        c.case(f'PUT /categories/1 {name}', 'PUT', '/categories/1', body=body, exp_o=eo,
               exp_r=REJ(st, msg, has={'post.get.json.0.name': 'Backend', 'post.get.json.0.color': '#3498db'}),
               cls=cls, reseed=True, post=counts_post('/categories'))
    c.case('PUT /categories/999', 'PUT', '/categories/999', body={'name': 'x'}, exp=REJ(404, 'Categoria não encontrada'), reseed=True)
    c.case('DELETE /categories/1 com tasks', 'DELETE', '/categories/1', reseed=True,
           post=lambda cc: {'counts': counts(), 'tasks_cat_null': q('SELECT COUNT(*) FROM tasks WHERE category_id IS NULL')[0][0],
                            'tasks_cat_1': q('SELECT COUNT(*) FROM tasks WHERE category_id=1')[0][0]},
           exp=S(200, has={'resp.json': {'message': 'Categoria deletada'}, 'post.counts': {'tasks': 10, 'users': 3, 'categories': 3},
                           'post.tasks_cat_null': 6, 'post.tasks_cat_1': 0}, changed=True))
    c.case('DELETE /categories/5 sem tasks', 'DELETE', '/categories/5', reseed=True,
           setup=lambda cc: cc.raw('POST', '/categories', {'name': 'Vazia'}), post=counts_post(),
           exp=S(200, has={'post.counts.categories': 4, 'post.counts.tasks': 10}, changed=True))
    c.case('DELETE /categories/999', 'DELETE', '/categories/999', exp=REJ(404, 'Categoria não encontrada'), reseed=True)


# ------------------------------------------------------------------ grupos: autenticação
def _sign(payload, key=None):
    from itsdangerous import URLSafeTimedSerializer
    tok = URLSafeTimedSerializer(key or os.environ['SECRET_KEY'], salt=SALT).dumps(payload)
    note_secret(tok)
    return tok


def g_auth(c):
    put = {'name': 'Alterado'}
    changed_name = S(200, None, has={'resp.json.name': 'Alterado'}, changed=True)
    deny = lambda st, msg: REJ(st, msg, has={'post.get.json.name': 'Maria Santos'})  # noqa: E731
    c.case('auth PUT anonimo', 'PUT', '/users/2', body=put, exp_o=changed_name, cls='D-1a', reseed=True,
           post=counts_post('/users/2'),
           exp_r=merge(deny(401, 'Token ausente'), {'has': {'resp.www_authenticate': 'Bearer'}}))
    c.case('auth DELETE anonimo', 'DELETE', '/users/2', exp_o=S(200, changed=True), exp_r=REJ(401, 'Token ausente'),
           cls='D-1a', reseed=True)
    c.reseed()
    tM = c.tokens['M'] or 'x'
    bad = [('Bearer sem token', 'Bearer'), ('Basic', 'Basic abc'), ('dois espacos', 'Bearer  ' + tM), ('token vazio', 'Bearer '),
           ('adulterado', 'Bearer ' + tM[:-2] + ('A' if tM[-2] != 'A' else 'B') + tM[-1]),
           ('outra chave', 'Bearer ' + _sign({'uid': 2, 'sid': 'a' * 43}, key='chave-diferente-de-teste-com-32-caracteres')),
           ('longo demais', 'Bearer ' + 'a' * 5000)]
    for name, h in bad:
        c.case(f'auth header {name}', 'PUT', '/users/2', body=put, hdr={'Authorization': h}, exp_o=changed_name,
               exp_r=deny(401, 'Token inválido'), cls='D-1a', reseed=True, post=counts_post('/users/2'))
    c.reseed()
    c.case('auth bearer minusculo valido', 'PUT', '/users/2', body=put, hdr={'Authorization': 'bearer ' + (c.tokens['M'] or '')},
           exp=changed_name)
    if not ORIG:
        c.reseed()
        n2 = nonce_of(2)
        payloads = [('uid str', {'uid': '2', 'sid': n2}), ('uid bool', {'uid': True, 'sid': n2}), ('uid 0', {'uid': 0, 'sid': n2}),
                    ('uid negativo', {'uid': -1, 'sid': n2}), ('uid 2^63', {'uid': H, 'sid': n2}),
                    ('uid -2^63-1', {'uid': -H - 1, 'sid': n2}), ('sem sid', {'uid': 2}),
                    ('sid curto', {'uid': 2, 'sid': 'abc'}), ('sid caracteres', {'uid': 2, 'sid': '!' * 43}),
                    ('sid com \\n final', {'uid': 2, 'sid': n2 + '\n'}), ('chave extra', {'uid': 2, 'sid': n2, 'x': 1}),
                    ('payload lista', [2, n2]), ('uid inexistente', {'uid': 999, 'sid': n2}),
                    ('sid de outro', {'uid': 2, 'sid': nonce_of(1)})]
        for name, pl in payloads:
            c.case(f'auth payload {name}', 'PUT', '/users/2', body=put, hdr={'Authorization': 'Bearer ' + _sign(pl)},
                   exp_r=deny(401, 'Token inválido'), cls='D-1a', post=counts_post('/users/2'), only='refatorado')
        c.case('auth payload valido assinado pelo harness', 'PUT', '/users/2', body=put,
               hdr={'Authorization': 'Bearer ' + _sign({'uid': 2, 'sid': n2})}, exp_r=changed_name, only='refatorado')
        import time
        app_exp = make_app({'TOKEN_MAX_AGE': 1})
        cl = app_exp.test_client()
        tok = cl.post('/login', json={'email': M_EMAIL, 'password': CRED[M_EMAIL]}).get_json()['token']
        note_secret(tok)
        time.sleep(2.2)
        r2 = cl.put('/users/2', json=put, headers={'Authorization': 'Bearer ' + tok})
        c.fact('auth token expirado', [r2.status_code, (r2.get_json() or {}).get('error')], exp=[401, 'Token expirado'],
               only='refatorado')
    M = [('proprio altera nome', 'PUT', '/users/2', {'name': 'Maria X'}, 'M', None, {'resp.json.name': 'Maria X'}),
         ('proprio altera email', 'PUT', '/users/2', {'email': 'mx@email.com'}, 'M', None, {'resp.json.email': 'mx@email.com'}),
         ('proprio altera senha', 'PUT', '/users/2', {'password': PW['nova']}, 'M', None, {}),
         ('outro usuario', 'PUT', '/users/3', {'name': 'X'}, 'M', (403, 'Permissão negada'), None),
         ('proprio role diferente', 'PUT', '/users/2', {'role': 'admin'}, 'M', (403, 'Permissão negada'), None),
         ('proprio role igual', 'PUT', '/users/2', {'role': 'user'}, 'M', None, {'resp.json.role': 'user'}),
         ('proprio active diferente', 'PUT', '/users/2', {'active': False}, 'M', (403, 'Permissão negada'), None),
         ('proprio active igual', 'PUT', '/users/2', {'active': True}, 'M', None, {'resp.json.active': True}),
         ('manager outro', 'PUT', '/users/2', {'name': 'X'}, 'P', (403, 'Permissão negada'), None),
         ('admin outro role', 'PUT', '/users/2', {'role': 'manager'}, 'A', None, {'resp.json.role': 'manager'}),
         ('admin outro active', 'PUT', '/users/2', {'active': False}, 'A', None, {'resp.json.active': False}),
         ('delete proprio user', 'DELETE', '/users/2', None, 'M', (403, 'Permissão negada'), None),
         ('delete outro user', 'DELETE', '/users/3', None, 'M', (403, 'Permissão negada'), None),
         ('delete admin outro', 'DELETE', '/users/2', None, 'A', None, {'resp.json.message': 'Usuário deletado com sucesso'}),
         ('admin rebaixa a si mesmo', 'PUT', '/users/1', {'role': 'user'}, 'A', None, {'resp.json.role': 'user'}),
         ('admin inativa a si mesmo', 'PUT', '/users/1', {'active': False}, 'A', None, {'resp.json.active': False}),
         ('admin exclui a si mesmo (ultimo admin)', 'DELETE', '/users/1', None, 'A', None, {'post.counts.users': 2})]
    for name, m, p, body, who, denied, has in M:
        kw = {} if body is None else {'body': body}
        ok_spec = S(200, None, has=has or {}, changed=True if (has is not None and (has or m == 'DELETE' or body)) else None)
        if ok_spec.get('changed') is None:
            ok_spec.pop('changed')
        if name in ('proprio role igual', 'proprio active igual'):
            ok_spec.pop('changed', None)
            ok_spec['unchanged'] = True
        exp_o = S(200)
        exp_r = REJ(*denied) if denied else ok_spec
        c.case(f'matriz {name}', m, p, hdr=who, exp_o=exp_o, exp_r=exp_r, cls='D-1a' if denied else None, reseed=True,
               post=counts_post(), **kw)
    c.reseed()
    tokP = c.tokens['P']
    c.raw('PUT', '/users/3', {'active': False}, hdr=c.bearer('A'))
    c.case('inativo usa token', 'PUT', '/users/3', body={'name': 'P'}, hdr={'Authorization': f'Bearer {tokP}'},
           exp_o=S(200), exp_r=REJ(403, 'Usuário inativo'), cls='D-1a')
    c.case('inativo POST /users com bearer', 'POST', '/users', body={'name': 'N', 'email': 'n@email.com', 'password': PW['outra']},
           hdr={'Authorization': f'Bearer {tokP}'}, exp_o=S(201), exp_r=REJ(403, 'Usuário inativo', has={'post.counts.users': 3}),
           cls='D-1a', post=counts_post())
    c.raw('PUT', '/users/3', {'active': True}, hdr=c.bearer('A'))
    c.case('reativado usa token', 'PUT', '/users/3', body={'name': 'P'}, hdr={'Authorization': f'Bearer {tokP}'},
           exp=S(200, None, has={'resp.json.name': 'P'}))
    c.reseed()
    tokM = c.tokens['M']
    c.raw('PUT', '/users/2', {'role': 'admin'}, hdr=c.bearer('A'))
    c.case('promovido opera como admin', 'PUT', '/users/3', body={'name': 'P2'}, hdr={'Authorization': f'Bearer {tokM}'},
           exp=S(200, None, has={'resp.json.name': 'P2'}, changed=True))
    c.raw('PUT', '/users/2', {'role': 'user'}, hdr=c.bearer('A'))
    c.case('rebaixado perde admin na hora', 'PUT', '/users/3', body={'name': 'P3'}, hdr={'Authorization': f'Bearer {tokM}'},
           exp_o=S(200), exp_r=REJ(403, 'Permissão negada'), cls='D-1a')
    c.reseed()
    tokX = c.tokens['P']
    c.raw('DELETE', '/users/3', hdr=c.bearer('A'))
    c.case('POST /users bearer de conta excluida', 'POST', '/users',
           body={'name': 'N', 'email': 'n@email.com', 'password': PW['outra']}, hdr={'Authorization': f'Bearer {tokX}'},
           exp_o=S(201), exp_r=REJ(401, 'Token inválido', has={'post.counts.users': 2}), cls='D-1a', post=counts_post())


def g_ciclo_token(c):
    for variante, y_role, hdr_y in [('Y user', 'user', None), ('Y admin', 'admin', 'A')]:
        c.reseed()
        r = c.raw('POST', '/users', {'name': 'X', 'email': 'x@email.com', 'password': PW['outra']})
        x_id = (r.get('json') or {}).get('id')
        tokX = c.login('x@email.com', PW['outra'])
        c.raw('DELETE', f'/users/{x_id}', hdr=c.bearer('A'))
        body = {'name': 'Y', 'email': 'y@email.com', 'password': PW['nova'], 'role': y_role}
        r = c.raw('POST', '/users', body, hdr=c.bearer(hdr_y) if hdr_y else None)
        y_id = (r.get('json') or {}).get('id')
        c.fact(f'reuso de ID ({variante}): Y recebeu o mesmo ID de X', y_id == x_id and y_id is not None, exp=True)
        target, method = ('/users/2', 'DELETE') if y_role == 'admin' else (f'/users/{y_id}', 'PUT')
        c.case(f'reuso de ID ({variante}): token antigo de X', method, target,
               body=MISSING if method == 'DELETE' else {'name': 'Hackeado'}, hdr={'Authorization': f'Bearer {tokX}'},
               exp_o=S(200), exp_r=REJ(401, 'Token inválido', has={'post.y': [['Y', y_role]]}), cls='D-1a',
               post=lambda cc, yid=y_id: {'y': [list(r) for r in q('SELECT name, role FROM users WHERE id=?', (yid,))], 'counts': counts()})
        tokY = c.login('y@email.com', PW['nova'])
        c.case(f'reuso de ID ({variante}): controle com token novo de Y', 'PUT', f'/users/{y_id}', body={'name': 'Y2'},
               hdr={'Authorization': f'Bearer {tokY}'}, exp=S(200, None, has={'resp.json.name': 'Y2', 'resp.json.id': y_id}))
    c.reseed()
    tokA = c.tokens['A']
    n_before = nonce_of(1)
    c.reseed(login=False)
    c.fact('novo seed: admin mantém id 1', q(f"SELECT id FROM users WHERE email='{A_EMAIL}'")[0][0], exp=1)
    c.fact('novo seed: nonce do admin mudou', n_before != nonce_of(1) and nonce_of(1) is not None, exp=True, only='refatorado')
    c.case('novo seed: token antigo do admin', 'PUT', '/users/2', body={'name': 'Z'}, hdr={'Authorization': f'Bearer {tokA}'},
           exp_o=S(200), exp_r=REJ(401, 'Token inválido'), cls='D-1a')
    c.login_all()
    c.case('novo seed: token novo do admin', 'PUT', '/users/2', body={'name': 'Z'}, hdr='A', exp=S(200, None, has={'resp.json.name': 'Z'}))
    c.reseed()
    T1 = c.login(M_EMAIL, CRED[M_EMAIL])
    T2 = c.login(M_EMAIL, CRED[M_EMAIL])
    c.case('senha: troca com T1', 'PUT', '/users/2', body={'password': PW['nova']}, hdr={'Authorization': f'Bearer {T1}'},
           exp=S(200, None, changed=True))
    for tn, tv in [('T1', T1), ('T2', T2)]:
        c.case(f'senha: {tn} depois da troca', 'PUT', '/users/2', body={'name': 'M'}, hdr={'Authorization': f'Bearer {tv}'},
               exp_o=S(200), exp_r=REJ(401, 'Token inválido'), cls='D-1a')
    c.case('senha: login com a antiga', 'POST', '/login', body={'email': M_EMAIL, 'password': CRED[M_EMAIL]},
           exp=S(401, 'Credenciais inválidas'))
    T3 = c.login(M_EMAIL, PW['nova'])
    c.case('senha: token novo funciona', 'PUT', '/users/2', body={'name': 'M3'}, hdr={'Authorization': f'Bearer {T3}'},
           exp=S(200, None, has={'resp.json.name': 'M3'}))
    c.reseed()
    tokP = c.tokens['P']
    c.case('senha: admin troca senha de pedro', 'PUT', '/users/3', body={'password': PW['nova2']}, hdr='A', exp=S(200, None, changed=True))
    c.case('senha: token antigo de pedro', 'PUT', '/users/3', body={'name': 'P'}, hdr={'Authorization': f'Bearer {tokP}'},
           exp_o=S(200), exp_r=REJ(401, 'Token inválido'), cls='D-1a')
    c.case('senha: token do admin continua', 'PUT', '/users/2', body={'name': 'M'}, hdr='A', exp=S(200, None, has={'resp.json.name': 'M'}))
    c.reseed()
    T1 = c.login(M_EMAIL, CRED[M_EMAIL])
    before = q('SELECT password FROM users WHERE id=2')[0][0], nonce_of(2)
    from sqlalchemy import event, exc
    from sqlalchemy.orm import Session

    def boom(session, ctx_, inst):
        raise exc.OperationalError('forcado', None, Exception('falha forcada de flush'))
    event.listen(Session, 'before_flush', boom)
    try:
        c.case('senha: commit falha (induzida)', 'PUT', '/users/2', body={'password': PW['nova2']},
               hdr={'Authorization': f'Bearer {T1}'}, exp=REJ(500, 'Erro ao atualizar'))
    finally:
        event.remove(Session, 'before_flush', boom)
    c.fact('senha: commit falho mantém hash e nonce', (q('SELECT password FROM users WHERE id=2')[0][0], nonce_of(2)) == before, exp=True)
    c.case('senha: T1 continua válido após falha', 'PUT', '/users/2', body={'name': 'M'}, hdr={'Authorization': f'Bearer {T1}'},
           exp=S(200, None, has={'resp.json.name': 'M'}))
    c.reseed()
    q('UPDATE users SET password=? WHERE id=2', (hashlib.md5(CRED[M_EMAIL].encode()).hexdigest(),))
    T0 = c.login(M_EMAIL, CRED[M_EMAIL]) if not ORIG else None
    n0 = nonce_of(2)
    c.fact('md5 legado: formato do hash após login', hash_kind(M_EMAIL), exp='md5' if ORIG else 'werkzeug-scrypt', cls='D-2a')
    c.fact('md5 legado: nonce mantido', nonce_of(2) == n0, exp=True, only='refatorado')
    if not ORIG:
        c.case('md5 legado: token anterior continua', 'PUT', '/users/2', body={'name': 'Maria Santos'},
               hdr={'Authorization': f'Bearer {T0}'}, exp_r=S(200), only='refatorado')
    c.case('md5 legado: login seguinte', 'POST', '/login', body={'email': M_EMAIL, 'password': CRED[M_EMAIL]},
           exp=S(200, None, has={'resp.json.user.id': 2}), cls='D-1a')
    c.case('md5 legado: senha errada', 'POST', '/login', body={'email': M_EMAIL, 'password': PW['errada']},
           exp=S(401, 'Credenciais inválidas'))
    md5a = hashlib.md5(CRED[A_EMAIL].encode()).hexdigest()
    for name, h in [('vazio', ''), ('abc', 'abc'), ('werkzeug truncado', 'scrypt:32768:8:1$abc'), ('md5 31', md5a[:31]),
                    ('md5 maiusculo', md5a.upper()), ('md5 com \\n final', md5a + '\n')]:
        c.case(f'hash malformado {name}', 'POST', '/login', body={'email': A_EMAIL, 'password': CRED[A_EMAIL]},
               exp=S(401, 'Credenciais inválidas'), reseed=True, setup=lambda cc, h=h: q('UPDATE users SET password=? WHERE id=1', (h,)))


def g_rollback(c):
    from sqlalchemy import event, exc
    from sqlalchemy.orm import Session

    def conflict_once(email):
        state = {'done': False}

        def hook(session, ctx_, inst):
            if not state['done']:
                state['done'] = True
                cols = columns('users')
                extra = ['auth_nonce'] if 'auth_nonce' in cols else []
                names = ['name', 'email', 'password', 'role', 'active', 'created_at'] + extra
                vals = ['Corrida', email, 'f' * 32, 'user', 1, fmt(now_naive())] + ['n' * 43] * len(extra)
                con = sqlite3.connect(DBP)
                con.execute(f'INSERT INTO users ({",".join(names)}) VALUES ({",".join("?" * len(vals))})', vals)
                con.commit()
                con.close()
        return hook
    def full_state(email, user_path):
        def f(cc):
            out = counts_post(user_path)(cc)
            out['users'] = cc.raw('GET', '/users').get('json')
            out['tasks'] = cc.raw('GET', '/tasks').get('json')
            out['categories'] = cc.raw('GET', '/categories').get('json')
            out['corrida'] = [list(r) for r in q('SELECT name, email, role FROM users WHERE email=?', (email,))]
            return out
        return f

    def c07(status, msg, email, user_has):
        """Só a linha concorrente pode surgir; todo o resto do estado público deve ser igual ao anterior."""
        has = {'post.counts': {'tasks': 10, 'users': 4, 'categories': 4}, 'post.corrida': [['Corrida', email, 'user']]}
        has.update(user_has)
        return S(status, msg, has=has, pre_eq={'post.get': None, 'post.tasks': None, 'post.categories': None,
                                                'post.users': {'drop_email': email}})
    c.reseed()
    h = conflict_once('corrida@email.com')
    event.listen(Session, 'before_flush', h)
    try:
        c.case('conflito forçado POST /users', 'POST', '/users',
               body={'name': 'Conflito', 'email': 'corrida@email.com', 'password': PW['cadastro']},
               exp_o=c07(500, 'Erro ao criar usuário', 'corrida@email.com', {'post.get.json.role': 'admin'}),
               exp_r=c07(409, 'Email já cadastrado', 'corrida@email.com', {'post.get.json.role': 'admin'}),
               cls='C-07', post=full_state('corrida@email.com', '/users/1'))
    finally:
        event.remove(Session, 'before_flush', h)
    c.case('recuperação da aplicação após conflito', 'GET', '/users', exp=S(200, len={'resp.json': 4}))
    c.reseed()
    h = conflict_once('corrida2@email.com')
    event.listen(Session, 'before_flush', h)
    try:
        c.case('conflito forçado PUT /users/2', 'PUT', '/users/2', body={'email': 'corrida2@email.com'}, hdr='A',
               exp_o=c07(500, 'Erro ao atualizar', 'corrida2@email.com', {
                   'post.get.json.email': M_EMAIL, 'post.get.json.role': 'user', 'post.get.json.name': 'Maria Santos'}),
               exp_r=c07(409, 'Email já cadastrado', 'corrida2@email.com', {
                   'post.get.json.email': M_EMAIL, 'post.get.json.role': 'user', 'post.get.json.name': 'Maria Santos'}),
               cls='C-07', post=full_state('corrida2@email.com', '/users/2'))
    finally:
        event.remove(Session, 'before_flush', h)
    c.case('recuperação da aplicação após conflito PUT', 'PUT', '/users/2', body={'name': 'Ok'}, hdr='A',
           exp=S(200, None, has={'resp.json.name': 'Ok'}))
    c.reseed()

    def boom(session, ctx_, inst):
        raise exc.OperationalError('forcado', None, Exception('falha forcada de flush'))
    event.listen(Session, 'before_flush', boom)
    try:
        c.case('falha forçada de flush POST /tasks (induzida)', 'POST', '/tasks', body={'title': 'Falha'},
               exp=REJ(500, 'Erro ao criar task'))
    finally:
        event.remove(Session, 'before_flush', boom)
    c.case('recuperação da aplicação após falha de flush', 'POST', '/tasks', body={'title': 'Depois'},
           exp=S(201, None, has={'resp.json.id': 11, 'resp.json.title': 'Depois'}))
    if not ORIG:
        from database import db, commit_or_rollback
        from errors import ConflictError
        from models.user import User
        c.reseed()
        with c.app.app_context():
            s = db.session()
            u = User(name='Dup', email=A_EMAIL, role='user')
            u.set_password(PW['outra'])
            db.session.add(u)
            got = None
            try:
                commit_or_rollback('Erro ao criar usuário')
            except ConflictError as e:
                got = str(e)
            same, active = db.session() is s, s.is_active
            u2 = User(name='Valido', email='valido@email.com', role='user')
            u2.set_password(PW['outra'])
            s.add(u2)
            commit_or_rollback('Erro ao criar usuário')
        c.fact('mesma sessão: ConflictError', got, exp='Email já cadastrado', only='refatorado')
        c.fact('mesma sessão: mesmo objeto de sessão', same, exp=True, only='refatorado')
        c.fact('mesma sessão: sessão ativa após rollback', active, exp=True, only='refatorado')
        c.fact('mesma sessão: commit seguinte persistiu', q("SELECT COUNT(*) FROM users WHERE email='valido@email.com'")[0][0],
               exp=1, only='refatorado')


def g_seed_falha(c):
    c.reseed(login=False)
    q("INSERT INTO categories (name, description, color, created_at) VALUES ('Marcador','m','#999999',?)", (fmt(now_naive()),))
    q("INSERT INTO tasks (title, status, priority, created_at, updated_at) VALUES ('Tarefa marcadora','pending',3,?,?)",
      (fmt(now_naive()), fmt(now_naive())))
    before = db_state()
    before_counts = counts()
    from database import db
    from models.task import Task
    orig_add = db.session.add
    n = {'tasks': 0}

    def add(obj, *a, **k):
        if isinstance(obj, Task):
            n['tasks'] += 1
            if n['tasks'] == 5:
                raise RuntimeError('falha induzida na 5a task')
        return orig_add(obj, *a, **k)
    db.session.add = add
    err = None
    try:
        run_seed(c.app)
    except Exception as e:  # noqa
        err = type(e).__name__
    finally:
        db.session.add = orig_add
        with c.app.app_context():
            db.session.remove()
    c.fact('seed falha: exceção propagada', err, exp='RuntimeError')
    c.fact('seed falha: contagens antes', before_counts, exp={'tasks': 11, 'users': 3, 'categories': 5})
    c.fact('seed falha: banco idêntico ao anterior', db_state() == before, exp=False if ORIG else True, cls='F-06')
    c.fact('seed falha: contagens depois', counts(), exp={'tasks': 0, 'users': 3, 'categories': 4} if ORIG else before_counts,
           cls='F-06')


# ------------------------------------------------------------------ grupos novos da rodada 2
def g_bigint(c):
    c.reseed()
    for m, p, hdr, msg in [('GET', f'/tasks/{H}', None, 'Task não encontrada'), ('GET', f'/users/{H}', None, 'Usuário não encontrado'),
                           ('GET', f'/users/{H}/tasks', None, 'Usuário não encontrado'),
                           ('GET', f'/reports/user/{H}', None, 'Usuário não encontrado'),
                           ('PUT', f'/tasks/{H}', None, 'Task não encontrada'), ('DELETE', f'/tasks/{H}', None, 'Task não encontrada'),
                           ('PUT', f'/categories/{H}', None, 'Categoria não encontrada'),
                           ('DELETE', f'/categories/{H}', None, 'Categoria não encontrada'),
                           ('PUT', f'/users/{H}', 'A', 'Usuário não encontrado'), ('DELETE', f'/users/{H}', 'A', 'Usuário não encontrado')]:
        kw = {'body': {'title': 'abc', 'name': 'x'}} if m == 'PUT' else {}
        c.case(f'2^63 {m} {p.replace(str(H), "<2^63>")}', m, p, hdr=hdr, exp_o='medir',
               exp_r=REJ(404, msg, write=m != 'GET'), cls='C-12', **kw)
    for qs, ids in [(f'priority={H}', []), (f'user_id={H}', []), (f'priority=-{H + 1}', []), (f'user_id={H}&priority=2', [])]:
        c.case(f'2^63 GET /tasks/search?{qs.replace(str(H + 1), "<2^63+1>").replace(str(H), "<2^63>")}', 'GET',
               f'/tasks/search?{qs}', exp_o='medir', exp_r=S(200, has={'resp.json': ids}), cls='C-12')
    c.case('2^63-1 GET /tasks/<max> (dentro da faixa)', 'GET', f'/tasks/{H - 1}', exp=S(404, 'Task não encontrada'))
    c.case('2^63-1 GET /tasks/search?user_id=<max>', 'GET', f'/tasks/search?user_id={H - 1}', exp=S(200, has={'resp.json': []}))


def g_http(c):
    c.reseed()
    for m, p, allow in [('POST', '/', ['GET', 'HEAD', 'OPTIONS']), ('DELETE', '/tasks', ['GET', 'HEAD', 'OPTIONS', 'POST']),
                        ('PATCH', '/tasks/1', ['DELETE', 'GET', 'HEAD', 'OPTIONS', 'PUT'])]:
        c.case(f'405 {m} {p}', m, p, exp_o=S(405, is_json=False, has={'resp.allow': allow}),
               exp_r=REJ(405, 'Método não permitido', has={'resp.allow': allow}), cls='M-03')
    bodies = [('json malformado', '{"title": ', 'application/json'), ('content-type texto', 'abc', 'text/plain')]
    for bname, raw, ct in bodies:
        for p, msg, hdr in [('/tasks/999', 'Task não encontrada', None), ('/categories/999', 'Categoria não encontrada', None),
                            ('/users/999', 'Usuário não encontrado', 'A')]:
            c.case(f'PUT {p} inexistente + {bname}', 'PUT', p, raw=raw, ctype=ct, hdr=hdr, exp=REJ(404, msg))
        c.case(f'PUT /users/999 anonimo + {bname}', 'PUT', '/users/999', raw=raw, ctype=ct, exp_o=S(404, 'Usuário não encontrado'),
               exp_r=REJ(401, 'Token ausente'), cls='D-1a')
        c.case(f'PUT /users/2 anonimo + {bname}', 'PUT', '/users/2', raw=raw, ctype=ct, exp_o=S(400 if 'malf' in bname else 415, is_json=False),
               exp_r=REJ(401, 'Token ausente'), cls='D-1a')
        st = 400 if 'malf' in bname else 415
        for p, hdr in [('/tasks/1', None), ('/categories/1', None), ('/users/2', 'A')]:
            c.case(f'PUT {p} existente + {bname}', 'PUT', p, raw=raw, ctype=ct, hdr=hdr, exp_o=S(st, is_json=False),
                   exp_r=REJ(st, 'Dados inválidos'), cls='C-JSON')


def g_fronteira7(c):
    """Janela de 7 dias e atraso com relógio controlado (antes, no limite, depois)."""
    c.reseed(login=False)
    q('DELETE FROM tasks')
    T = now_naive().replace(microsecond=0) - timedelta(hours=1)
    lim, us, old = T - timedelta(days=7), timedelta(microseconds=1), fmt(T - timedelta(days=30))
    rows = [  # título, status, created_at, updated_at, due_date
        ('criada antes do limite', 'pending', fmt(lim - us), fmt(lim - us), None),
        ('criada no limite', 'pending', fmt(lim), fmt(lim), None),
        ('criada depois do limite', 'pending', fmt(lim + us), fmt(lim + us), None),
        ('concluida antes do limite', 'done', old, fmt(lim - us), None),
        ('concluida no limite', 'done', old, fmt(lim), None),
        ('concluida depois do limite', 'done', old, fmt(lim + us), None),
        ('prazo igual a agora', 'pending', old, old, fmt(T)),
        ('prazo 1us antes de agora', 'pending', old, old, fmt(T - us)),
    ]
    for title, st, cr, up, due in rows:
        q('INSERT INTO tasks (title,status,priority,created_at,updated_at,due_date) VALUES (?,?,3,?,?,?)', (title, st, cr, up, due))
    if ORIG:
        import routes.report_routes as rr
        base = rr.datetime

        class FixedDT(base):
            @classmethod
            def utcnow(cls):
                return T
        rr.datetime = FixedDT
    else:
        import controllers.report_controller as rc
        base = rc.utc_now
        rc.utc_now = lambda: T
    try:
        c.case('fronteira 7 dias: /reports/summary com relógio fixo', 'GET', '/reports/summary', exp=S(200, has={
            'resp.json.recent_activity': {'tasks_created_last_7_days': 2, 'tasks_completed_last_7_days': 2},
            'resp.json.overdue.count': 1, 'resp.json.overdue.tasks.0.title': 'prazo 1us antes de agora',
            'resp.json.overdue.tasks.0.days_overdue': 0, 'resp.json.generated_at': str(T)}))
    finally:
        if ORIG:
            rr.datetime = base
        else:
            rc.utc_now = base


def g_marcador(c):
    c.reseed(login=False)
    q("INSERT INTO categories (name, description, color, created_at) VALUES ('Marcador','m','#999999',?)", (fmt(now_naive()),))
    c.fact('marcador criado', counts(), exp={'tasks': 10, 'users': 3, 'categories': 5})


GROUPS = {'seed_leitura': g_seed_leitura, 'vazio': g_vazio, 'bordas': g_bordas, 'tasks_escrita': g_tasks_escrita,
          'users_escrita': g_users_escrita, 'categories_escrita': g_categories_escrita, 'auth': g_auth,
          'ciclo_token': g_ciclo_token, 'rollback': g_rollback, 'seed_falha': g_seed_falha, 'bigint': g_bigint,
          'http': g_http, 'fronteira7': g_fronteira7, 'marcador': g_marcador}


def main():
    ctx = Ctx()
    GROUPS[GROUP](ctx)
    if not ctx.records:
        print(f'{GROUP}: execução vazia', file=sys.__stdout__)
        sys.exit(1)
    with open(OUT, 'w') as fh:
        json.dump({'mode': MODE, 'group': GROUP, 'records': ctx.records}, fh, ensure_ascii=False, indent=1, default=str)
    bad = [r for r in ctx.records if r['errs']]
    print(f'{GROUP}: {len(ctx.records)} registros; com falha: {len(bad)}', file=sys.__stdout__)
    for b in bad:
        print('  FALHOU:', b['name'], '|', '; '.join(b['errs'])[:300], file=sys.__stdout__)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
