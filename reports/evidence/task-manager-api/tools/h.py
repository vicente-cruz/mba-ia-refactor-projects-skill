# Versão sanitizada: senhas de teste substituídas por <removido> (não executável como está).
# Hashes SHA-256 das versões efetivamente executadas: SHA256SUMS-executados.txt
"""Harness de validação do task-manager-api (original x refatorado).

Uso: python -I -B h.py <copia> <original|refatorado> <grupo> <saida.json>
Executa com cwd na cópia. Nunca roda no repositório.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

COPY, MODE, GROUP, OUT = sys.argv[1:5]
COPY = os.path.realpath(COPY)
sys.path.insert(0, COPY)
os.chdir(COPY)
ORIG = MODE == 'original'
DBP = os.path.join(COPY, 'instance', 'tasks.db')
SECRETS_FILE = os.path.join(os.path.dirname(OUT), 'segredos-emitidos.txt')
MISSING = object()
TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$')
TS_KEYS = {'created_at', 'updated_at', 'generated_at', 'timestamp', 'due_date'}
SALT = 'task-manager-auth'
FIXED_TS = '2026-01-01 00:00:00.000000'


def now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def note_secret(value):
    if value:
        with open(SECRETS_FILE, 'a') as fh:
            fh.write(str(value) + '\n')


# ---------------------------------------------------------------- app/seed
_APP = None


def make_app(overrides=None, fresh=False):
    global _APP
    import app as appmod
    if ORIG:
        _APP = appmod.app
        return _APP
    if _APP is None or fresh or overrides:
        a = appmod.create_app(overrides or {})
        if not overrides:
            _APP = a
        return a
    return _APP


def seed_passwords():
    return {
        'SEED_ADMIN_PASSWORD': os.environ.get('SEED_ADMIN_PASSWORD'),
        'SEED_USER_PASSWORD': os.environ.get('SEED_USER_PASSWORD'),
        'SEED_MANAGER_PASSWORD': os.environ.get('SEED_MANAGER_PASSWORD'),
    }


def run_seed(app):
    import io
    import contextlib
    import seed
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if ORIG:
            seed.seed_data()
        else:
            seed.seed_data(app, seed.read_seed_passwords(os.environ))
    return buf.getvalue()


# ---------------------------------------------------------------- sqlite direto
def q(sql, args=()):
    con = sqlite3.connect(DBP)
    try:
        cur = con.execute(sql, args)
        rows = cur.fetchall()
        con.commit()
        return rows
    finally:
        con.close()


def columns(table):
    return [r[1] for r in q(f'PRAGMA table_info({table})')]


def counts():
    return {t: q(f'SELECT COUNT(*) FROM {t}')[0][0] for t in ('tasks', 'users', 'categories')}


def snapshot(exclude_cols=('auth_nonce',)):
    snap = {}
    for t in ('users', 'categories', 'tasks'):
        cols = [c for c in columns(t) if c not in exclude_cols]
        snap[t] = {'cols': cols, 'rows': q(f'SELECT {",".join(cols)} FROM {t} ORDER BY id')}
    return snap


def snap_digest(snap):
    return hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()


def hash_kind(email):
    rows = q('SELECT password FROM users WHERE email=?', (email,))
    if not rows:
        return None
    h = rows[0][0] or ''
    if re.fullmatch(r'[0-9a-f]{32}', h):
        return 'md5'
    if h.startswith('scrypt:'):
        return 'werkzeug-scrypt'
    if h.startswith('pbkdf2:'):
        return 'werkzeug-pbkdf2'
    return 'outro'


def nonce_of(uid):
    if 'auth_nonce' not in columns('users'):
        return None
    r = q('SELECT auth_nonce FROM users WHERE id=?', (uid,))
    return r[0][0] if r else None


# ---------------------------------------------------------------- normalização
def normalize(obj, flags):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in TS_KEYS and v is not None:
                if isinstance(v, str) and TS_RE.match(v):
                    out[k] = '<ts>'
                else:
                    flags.append(f'formato-temporal-invalido:{k}')
                    out[k] = '<TS_INVALIDO>'
            elif k == 'password':
                out[k] = '<presente>'
            elif k == 'auth_nonce':
                out[k] = '<presente>'
            elif k == 'token':
                note_secret(v)
                out[k] = '<fake-token>' if isinstance(v, str) and v.startswith('fake-jwt-token-') else '<token>'
            else:
                out[k] = normalize(v, flags)
        return out
    if isinstance(obj, list):
        return [normalize(x, flags) for x in obj]
    return obj


# ---------------------------------------------------------------- requisições
class Ctx:
    def __init__(self):
        self.app = make_app()
        self.client = self.app.test_client()
        self.tokens = {}
        self.records = []

    def reseed(self, login=True):
        run_seed(self.app)
        if login:
            self.login_all()

    def login(self, email, pw):
        r = self.client.post('/login', json={'email': email, 'password': pw})
        js = r.get_json(silent=True) or {}
        tok = js.get('token')
        note_secret(tok)
        return tok

    def login_all(self):
        self.tokens = {
            'A': self.login('joao@email.com', '<removido>'),
            'M': self.login('maria@email.com', '<removido>'),
            'P': self.login('pedro@email.com', '<removido>'),
        }

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
        js = r.get_json(silent=True) if 'json' in ct else None
        res = {'status': r.status_code, 'is_json': 'application/json' in ct}
        if js is not None:
            res['json'] = js
        else:
            txt = r.get_data(as_text=True)
            res['text'] = txt[:80]
        if r.headers.get('WWW-Authenticate'):
            res['www_authenticate'] = r.headers.get('WWW-Authenticate')
        return res

    def case(self, name, method, path, body=MISSING, raw=None, ctype=None, hdr=None,
             exp=None, exp_o=None, exp_r=None, cls=None, qc=False, reseed=False, post=None, setup=None):
        if reseed:
            self.reseed()
        if setup:
            setup(self)
        if isinstance(hdr, str):
            hdr = self.bearer(hdr)
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
        flags = []
        if 'json' in res:
            res['json'] = normalize(res['json'], flags)
        rec = {'name': name, 'method': method, 'path': path,
               'input': '<raw>' + raw if raw is not None else (None if body is MISSING else body),
               'resp': res, 'flags': flags}
        if n_q is not None:
            rec['queries'] = n_q
        if post:
            rec['post'] = post(self)
        e = exp_o if (ORIG and exp_o is not None) else exp_r if (not ORIG and exp_r is not None) else exp
        rec['exp'] = e
        rec['exp_ok'] = check_exp(e, res)
        rec['cls'] = cls
        self.records.append(rec)
        return res

    def fact(self, name, value, exp=None, cls=None):
        """Registro de uma verificação que não é uma requisição única."""
        ok = None if exp is None else (value == exp)
        self.records.append({'name': name, 'fact': value, 'exp': exp, 'exp_ok': ok, 'cls': cls})
        return value


def check_exp(e, res):
    if e is None or e == 'medir':
        return None
    if isinstance(e, int):
        return res['status'] == e
    st, msg = e
    if res['status'] != st:
        return False
    if msg is None:
        return True
    return isinstance(res.get('json'), dict) and res['json'].get('error') == msg


def get(path):
    return lambda c: c.raw('GET', path)


def get_counts(path=None):
    def f(c):
        out = {'counts': counts()}
        if path:
            r = c.raw('GET', path)
            fl = []
            out['get'] = {'status': r['status'], 'json': normalize(r.get('json'), fl)}
        return out
    return f


# ---------------------------------------------------------------- grupos
def g_seed_leitura(c):
    c.reseed()
    c.fact('db_path', os.path.relpath(_db_url_path(c.app), COPY))
    c.case('GET /', 'GET', '/', exp=200)
    c.case('GET /health', 'GET', '/health', exp=200)
    c.case('GET /tasks seed', 'GET', '/tasks', exp=200, qc=True)
    c.case('GET /tasks/1 atrasada', 'GET', '/tasks/1', exp=200)
    c.case('GET /tasks/2 nao atrasada', 'GET', '/tasks/2', exp=200)
    c.case('GET /tasks/999', 'GET', '/tasks/999', exp=(404, 'Task não encontrada'))
    c.case('GET /tasks/abc conversor', 'GET', '/tasks/abc', exp=404, cls='M-03')
    for qs, e, cls in [
        ('q=login', 200, None), ('q=%25', 200, None), ("q=x'%20OR%20'1'='1", 200, None),
        ('status=pending', 200, None), ('status=xyz', 200, None), ('priority=2', 200, None),
        ('priority=abc', {'o': 500, 'r': (400, 'Prioridade inválida')}, 'C-05'),
        ('priority=2.5', {'o': 500, 'r': (400, 'Prioridade inválida')}, 'C-05'),
        ('priority=%202%20', 200, None), ('priority=%2B2', 200, None),
        ('user_id=1', 200, None),
        ('user_id=abc', {'o': 500, 'r': (400, 'Usuário inválido')}, 'C-05'),
        ('q=a&status=pending&priority=1', 200, None), ('', 200, None),
        ('priority=1&priority=2', 200, None)]:
        if isinstance(e, dict):
            c.case(f'GET /tasks/search?{qs}', 'GET', f'/tasks/search?{qs}', exp_o=e['o'], exp_r=e['r'], cls=cls)
        else:
            c.case(f'GET /tasks/search?{qs}', 'GET', f'/tasks/search?{qs}', exp=e)
    c.case('GET /tasks/stats', 'GET', '/tasks/stats', exp=200)
    c.case('GET /users', 'GET', '/users', exp=200, qc=True)
    c.case('GET /users/1', 'GET', '/users/1', exp=200, cls='F-01')
    c.case('GET /users/999', 'GET', '/users/999', exp=(404, 'Usuário não encontrado'))
    c.case('GET /users/2/tasks', 'GET', '/users/2/tasks', exp=200)
    c.case('GET /users/999/tasks', 'GET', '/users/999/tasks', exp=(404, 'Usuário não encontrado'))
    c.case('GET /reports/summary', 'GET', '/reports/summary', exp=200, qc=True)
    c.case('GET /reports/user/1', 'GET', '/reports/user/1', exp=200)
    c.case('GET /reports/user/3', 'GET', '/reports/user/3', exp=200)
    c.case('GET /reports/user/999', 'GET', '/reports/user/999', exp=(404, 'Usuário não encontrado'))
    c.case('GET /categories', 'GET', '/categories', exp=200, qc=True)
    c.case('GET /nao-existe', 'GET', '/nao-existe', exp=404, cls='M-03')
    c.case('POST / metodo', 'POST', '/', exp=405, cls='M-03')


def _db_url_path(app):
    from database import db
    with app.app_context():
        return db.engine.url.database


def g_vazio(c):
    q('DELETE FROM tasks')
    q('DELETE FROM users')
    q('DELETE FROM categories')
    for p in ['/tasks', '/tasks/stats', '/users', '/reports/summary', '/categories', '/tasks/search']:
        c.case(f'vazio GET {p}', 'GET', p, exp=200, qc=p in ('/tasks', '/users', '/categories', '/reports/summary'))


def g_bordas(c):
    q('DELETE FROM tasks')
    q('DELETE FROM users')
    q('DELETE FROM categories')
    has_nonce = 'auth_nonce' in columns('users')
    n = now_naive()

    def ts(d):
        return (n + timedelta(days=d)).strftime('%Y-%m-%d %H:%M:%S.%f')
    for uid, name, email, role in [(1, 'Ana', 'ana@x.com', 'admin'), (2, 'Bia', 'bia@x.com', 'user')]:
        if has_nonce:
            q('INSERT INTO users (id,name,email,password,role,active,created_at,auth_nonce) VALUES (?,?,?,?,?,?,?,?)',
              (uid, name, email, hashlib.md5(b'<removido>').hexdigest(), role, 1, ts(-1), f'nonce{uid}'.ljust(43, 'x')))
        else:
            q('INSERT INTO users (id,name,email,password,role,active,created_at) VALUES (?,?,?,?,?,?,?)',
              (uid, name, email, hashlib.md5(b'<removido>').hexdigest(), role, 1, ts(-1)))
    q("INSERT INTO categories (id,name,description,color,created_at) VALUES (1,'Cat A','d','#111111',?)", (ts(-1),))
    q("INSERT INTO categories (id,name,description,color,created_at) VALUES (2,'Cat Vazia','d','#222222',?)", (ts(-1),))
    rows = [
        (1, 'Pendente atrasada', 'pending', 1, 1, 1, -3, -1, -1, None),
        (2, 'Em progresso atrasada', 'in_progress', 2, 1, 1, -1, -1, -1, 'a,b'),
        (3, 'Concluida atrasada', 'done', 5, 1, 1, -3, -10, -6, None),
        (4, 'Cancelada atrasada', 'cancelled', 4, 1, None, -3, -1, -1, None),
        (5, 'Sem vinculos', 'pending', 3, None, None, None, -8, -8, None),
        (6, 'Concluida antiga', 'done', 2, 1, 1, None, -8, -8, None),
        (7, 'Futura', 'pending', 3, None, 1, 5, -6, -6, None),
    ]
    for tid, title, st, pr, uid, cid, due, cr, up, tags in rows:
        q('INSERT INTO tasks (id,title,description,status,priority,user_id,category_id,created_at,updated_at,due_date,tags) '
          'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
          (tid, title, 'desc', st, pr, uid, cid, ts(cr), ts(up), ts(due) if due is not None else None, tags))
    c.case('bordas GET /tasks', 'GET', '/tasks', exp=200, qc=True)
    c.case('bordas GET /tasks/1', 'GET', '/tasks/1', exp=200)
    c.case('bordas GET /tasks/3 done atrasada', 'GET', '/tasks/3', exp=200)
    c.case('bordas GET /tasks/stats', 'GET', '/tasks/stats', exp=200)
    c.case('bordas GET /users', 'GET', '/users', exp=200, qc=True)
    c.case('bordas GET /users/2/tasks', 'GET', '/users/2/tasks', exp=200)
    c.case('bordas GET /users/1/tasks', 'GET', '/users/1/tasks', exp=200)
    c.case('bordas GET /reports/summary', 'GET', '/reports/summary', exp=200, qc=True)
    c.case('bordas GET /reports/user/1', 'GET', '/reports/user/1', exp=200)
    c.case('bordas GET /reports/user/2', 'GET', '/reports/user/2', exp=200)
    c.case('bordas GET /categories', 'GET', '/categories', exp=200, qc=True)
    c.case('bordas GET /tasks/search?user_id=1', 'GET', '/tasks/search?user_id=1', exp=200)


def _post_task_cases():
    t = 'Título válido'
    C = []
    # (nome, body | ('raw', texto, ctype), exp_o, exp_r, cls)
    C += [
        ('minimo', {'title': 'Nova task'}, 201, 201, None),
        ('completo', {'title': 'Completa', 'description': 'd', 'status': 'in_progress', 'priority': 2,
                      'user_id': 1, 'category_id': 1, 'due_date': '2030-01-15', 'tags': ['a', 'b']}, 201, 201, None),
        ('ctype texto', ('raw', 'abc', 'text/plain'), 'medir', (415, 'Dados inválidos'), 'C-xx json'),
        ('json malformado', ('raw', '{"title": ', 'application/json'), 'medir', (400, 'Dados inválidos'), 'C-xx json'),
        ('corpo null', None, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo {}', {}, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo []', [], (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo ""', '', (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo 0', 0, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo false', False, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo "x"', 'x', 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo true', True, 500, (400, 'Dados inválidos'), 'C-01'),
        ('title ausente', {'priority': 2}, (400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title null', {'title': None}, (400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title ""', {'title': ''}, (400, 'Título é obrigatório'), (400, 'Título é obrigatório'), None),
        ('title curto', {'title': 'ab'}, (400, 'Título muito curto'), (400, 'Título muito curto'), None),
        ('title longo', {'title': 'x' * 201}, (400, 'Título muito longo'), (400, 'Título muito longo'), None),
        ('title 200', {'title': 'y' * 200}, 201, 201, None),
        ('title numero', {'title': 5}, 500, (400, 'Título inválido'), 'C-02'),
        ('title true', {'title': True}, 500, (400, 'Título inválido'), 'C-02'),
        ('title lista 2', {'title': ['a', 'b']}, (400, 'Título muito curto'), (400, 'Título inválido'), 'C-02/M'),
        ('title lista 3', {'title': ['a', 'b', 'c']}, 'medir', (400, 'Título inválido'), 'C-02'),
        ('description numero', {'title': t, 'description': 5}, 'medir', (400, 'Descrição inválida'), 'R-02'),
        ('description true', {'title': t, 'description': True}, 'medir', (400, 'Descrição inválida'), 'R-02'),
        ('description lista', {'title': t, 'description': ['x']}, 'medir', (400, 'Descrição inválida'), 'C-10'),
        ('description objeto', {'title': t, 'description': {'a': 1}}, 'medir', (400, 'Descrição inválida'), 'C-10'),
        ('description null', {'title': t, 'description': None}, 201, 201, None),
        ('status invalido', {'title': t, 'status': 'xyz'}, (400, 'Status inválido'), (400, 'Status inválido'), None),
        ('status null', {'title': t, 'status': None}, (400, 'Status inválido'), (400, 'Status inválido'), None),
        ('status numero', {'title': t, 'status': 5}, (400, 'Status inválido'), (400, 'Status inválido'), None),
        ('priority false', {'title': t, 'priority': False}, (400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade inválida'), 'M-04'),
        ('priority true', {'title': t, 'priority': True}, 'medir', (400, 'Prioridade inválida'), 'R-03'),
        ('priority 2.0', {'title': t, 'priority': 2.0}, 'medir', 201, None),
        ('priority 2.5', {'title': t, 'priority': 2.5}, 'medir', (400, 'Prioridade inválida'), 'R-03'),
        ('priority NaN', ('raw', '{"title": "Título válido", "priority": NaN}', 'application/json'), 'medir', (400, 'Prioridade inválida'), 'R-03'),
        ('priority Infinity', ('raw', '{"title": "Título válido", "priority": Infinity}', 'application/json'), 'medir', (400, 'Prioridade inválida'), 'M-01'),
        ('priority -Infinity', ('raw', '{"title": "Título válido", "priority": -Infinity}', 'application/json'), 'medir', (400, 'Prioridade inválida'), 'M-01'),
        ('priority 0', {'title': t, 'priority': 0}, (400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('priority 6', {'title': t, 'priority': 6}, (400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('priority "2"', {'title': t, 'priority': '2'}, 500, (400, 'Prioridade inválida'), 'C-03'),
        ('priority null', {'title': t, 'priority': None}, 500, (400, 'Prioridade inválida'), 'C-03'),
        ('priority lista', {'title': t, 'priority': [1]}, 500, (400, 'Prioridade inválida'), 'C-03'),
        ('user_id 999', {'title': t, 'user_id': 999}, (404, 'Usuário não encontrado'), (404, 'Usuário não encontrado'), None),
        ('user_id 0', {'title': t, 'user_id': 0}, 201, (400, 'Usuário inválido'), 'R-04'),
        ('user_id false', {'title': t, 'user_id': False}, 201, (400, 'Usuário inválido'), 'R-04'),
        ('user_id ""', {'title': t, 'user_id': ''}, 201, (400, 'Usuário inválido'), 'R-04'),
        ('user_id "1"', {'title': t, 'user_id': '1'}, 'medir', (400, 'Usuário inválido'), 'R-04'),
        ('user_id true', {'title': t, 'user_id': True}, 'medir', (400, 'Usuário inválido'), 'R-04'),
        ('user_id -1', {'title': t, 'user_id': -1}, 'medir', (400, 'Usuário inválido'), 'M-02'),
        ('user_id 1.5', {'title': t, 'user_id': 1.5}, 'medir', (400, 'Usuário inválido'), 'M-02'),
        ('user_id "abc"', {'title': t, 'user_id': 'abc'}, 'medir', (400, 'Usuário inválido'), 'M-02'),
        ('user_id lista', {'title': t, 'user_id': [1]}, 'medir', (400, 'Usuário inválido'), 'C-11/M-02'),
        ('user_id objeto', {'title': t, 'user_id': {'id': 1}}, 'medir', (400, 'Usuário inválido'), 'C-11/M-02'),
        ('category_id 999', {'title': t, 'category_id': 999}, (404, 'Categoria não encontrada'), (404, 'Categoria não encontrada'), None),
        ('category_id 0', {'title': t, 'category_id': 0}, 201, (400, 'Categoria inválida'), 'R-04'),
        ('category_id "1"', {'title': t, 'category_id': '1'}, 'medir', (400, 'Categoria inválida'), 'R-04'),
        ('category_id -1', {'title': t, 'category_id': -1}, 'medir', (400, 'Categoria inválida'), 'M-02'),
        ('due_date invalida', {'title': t, 'due_date': '2030-13-01'}, (400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('due_date sem zero', {'title': t, 'due_date': '2030-1-5'}, 201, 201, None),
        ('due_date numero', {'title': t, 'due_date': 5}, (400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('due_date ""', {'title': t, 'due_date': ''}, 201, 201, None),
        ('due_date dd/mm', {'title': t, 'due_date': '15/01/2030'}, (400, 'Formato de data inválido. Use YYYY-MM-DD'), (400, 'Formato de data inválido. Use YYYY-MM-DD'), None),
        ('tags elemento numero', {'title': t, 'tags': [1]}, 500, (400, 'Tags inválidas'), 'C-04'),
        ('tags com virgula', {'title': t, 'tags': ['a,b']}, 201, (400, 'Tags inválidas'), 'R-05'),
        ('tags numero', {'title': t, 'tags': 5}, 'medir', (400, 'Tags inválidas'), 'R-05'),
        ('tags true', {'title': t, 'tags': True}, 'medir', (400, 'Tags inválidas'), 'R-05'),
        ('tags objeto', {'title': t, 'tags': {'a': 1}}, 'medir', (400, 'Tags inválidas'), 'C-04'),
        ('tags elemento vazio', {'title': t, 'tags': ['', 'x']}, 201, 201, None),
        ('tags string', {'title': t, 'tags': 'a,b'}, 201, 201, None),
        ('campos extras', {'title': t, 'id': 77, 'created_at': 'x', 'auth_nonce': 'y'}, 201, 201, None),
    ]
    return C


def _put_task_cases():
    C = [
        ('title', {'title': 'Novo título'}, 200, 200, None),
        ('description', {'description': 'nd'}, 200, 200, None),
        ('status', {'status': 'done'}, 200, 200, None),
        ('priority 5', {'priority': 5}, 200, 200, None),
        ('desvincula user', {'user_id': None}, 200, 200, None),
        ('desvincula category', {'category_id': None}, 200, 200, None),
        ('user 2', {'user_id': 2}, 200, 200, None),
        ('user 999', {'user_id': 999}, (404, 'Usuário não encontrado'), (404, 'Usuário não encontrado'), None),
        ('due null', {'due_date': None}, 200, 200, None),
        ('due valida', {'due_date': '2031-02-03'}, 200, 200, None),
        ('due invalida', {'due_date': 'bad'}, (400, 'Formato de data inválido'), (400, 'Formato de data inválido'), None),
        ('tags lista', {'tags': ['p', 'q']}, 200, 200, None),
        ('tags null', {'tags': None}, 200, 200, None),
        ('tags ""', {'tags': ''}, 200, 200, None),
        ('tags 0', {'tags': 0}, 'medir', 200, 'R-05/M'),
        ('tags false', {'tags': False}, 'medir', 200, 'R-05/M'),
        ('combinado titulo+prioridade invalida', {'title': 'Título Combinado', 'priority': 9},
         (400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade deve ser entre 1 e 5'), None),
        ('corpo {}', {}, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo null', None, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo "x"', 'x', 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo true', True, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo "title"', 'title', 500, (400, 'Dados inválidos'), 'C-01'),
        ('title null', {'title': None}, 500, (400, 'Título inválido'), 'C-02'),
        ('title numero', {'title': 5}, 500, (400, 'Título inválido'), 'C-02'),
        ('title false', {'title': False}, 500, (400, 'Título inválido'), 'C-02'),
        ('title ""', {'title': ''}, (400, 'Título muito curto'), (400, 'Título muito curto'), None),
        ('priority false', {'priority': False}, (400, 'Prioridade deve ser entre 1 e 5'), (400, 'Prioridade inválida'), 'M-04'),
        ('priority true', {'priority': True}, 'medir', (400, 'Prioridade inválida'), 'R-03'),
        ('priority "2"', {'priority': '2'}, 500, (400, 'Prioridade inválida'), 'C-03'),
        ('priority 2.5', {'priority': 2.5}, 'medir', (400, 'Prioridade inválida'), 'R-03'),
        ('user_id 0', {'user_id': 0}, 200, (400, 'Usuário inválido'), 'R-04'),
        ('description numero', {'description': 5}, 'medir', (400, 'Descrição inválida'), 'R-02'),
    ]
    return C


def g_tasks_escrita(c):
    for name, body, eo, er, cls in _post_task_cases():
        kw = {}
        if isinstance(body, tuple):
            kw = {'raw': body[1], 'ctype': body[2]}
        else:
            kw = {'body': body}
        c.case(f'POST /tasks {name}', 'POST', '/tasks', exp_o=eo, exp_r=er, cls=cls, reseed=True,
               post=get_counts('/tasks/11'), **kw)
    for name, body, eo, er, cls in _put_task_cases():
        c.case(f'PUT /tasks/1 {name}', 'PUT', '/tasks/1', body=body, exp_o=eo, exp_r=er, cls=cls, reseed=True,
               post=get_counts('/tasks/1'))
    c.case('PUT /tasks/999', 'PUT', '/tasks/999', body={'title': 'abc'}, exp=(404, 'Task não encontrada'), reseed=True)
    c.case('DELETE /tasks/1', 'DELETE', '/tasks/1', exp=(200, None), reseed=True, post=get_counts('/tasks/1'))
    c.case('DELETE /tasks/1 repetido', 'DELETE', '/tasks/1', exp=(404, 'Task não encontrada'))
    c.case('GET /tasks/stats apos criar e concluir', 'GET', '/tasks/stats', exp=200, reseed=True,
           setup=lambda cc: (cc.raw('POST', '/tasks', {'title': 'Para concluir'}),
                             cc.raw('PUT', '/tasks/11', {'status': 'done'})))


def g_users_escrita(c):
    ok = {'name': 'Novo', 'email': 'novo@email.com', 'password': '<removido>'}
    P = [
        ('sucesso', ok, None, 201, 201, None),
        ('duplicado', {**ok, 'email': 'joao@email.com'}, None, (409, 'Email já cadastrado'), (409, 'Email já cadastrado'), None),
        ('sem name', {'email': 'a@b.com', 'password': '<removido>'}, None, (400, 'Nome é obrigatório'), (400, 'Nome é obrigatório'), None),
        ('sem email', {'name': 'A', 'password': '<removido>'}, None, (400, 'Email é obrigatório'), (400, 'Email é obrigatório'), None),
        ('sem password', {'name': 'A', 'email': 'a@b.com'}, None, (400, 'Senha é obrigatória'), (400, 'Senha é obrigatória'), None),
        ('name numero', {**ok, 'name': 5}, None, 'medir', (400, 'Nome inválido'), 'R-06'),
        ('name lista', {**ok, 'name': ['a']}, None, 'medir', (400, 'Nome inválido'), 'C-10'),
        ('email numero', {**ok, 'email': 5}, None, 500, (400, 'Email inválido'), 'C-06'),
        ('email invalido', {**ok, 'email': 'bad'}, None, (400, 'Email inválido'), (400, 'Email inválido'), None),
        ('password numero', {**ok, 'password': 5}, None, 500, (400, 'Senha inválida'), 'C-06'),
        ('password curta', {**ok, 'password': 'abc'}, None, (400, 'Senha deve ter no mínimo 4 caracteres'), (400, 'Senha deve ter no mínimo 4 caracteres'), None),
        ('password lista', {**ok, 'password': ['a', 'b', 'c', 'd']}, None, 500, (400, 'Senha inválida'), 'C-06'),
        ('role invalido', {**ok, 'role': 'xyz'}, None, (400, 'Role inválido'), (400, 'Role inválido'), None),
        ('role null', {**ok, 'role': None}, None, (400, 'Role inválido'), (400, 'Role inválido'), None),
        ('role admin anonimo', {**ok, 'role': 'admin'}, None, 201, (401, 'Token ausente'), 'D-1a'),
        ('role admin com admin', {**ok, 'role': 'admin'}, 'A', 201, 201, None),
        ('role manager com user', {**ok, 'role': 'manager'}, 'M', 201, (403, 'Permissão negada'), 'D-1a'),
        ('role user com user', {**ok, 'role': 'user'}, 'M', 201, 201, None),
        ('active ignorado', {**ok, 'active': False}, None, 201, 201, None),
        ('bearer invalido em cadastro anonimo', ok, {'Authorization': 'Bearer xxx'}, 201, (401, 'Token inválido'), 'D-1a'),
        ('corpo null', None, None, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], None, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, None, 500, (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, hdr, eo, er, cls in P:
        def post(cc):
            out = get_counts()(cc)
            out['hash_novo'] = hash_kind('novo@email.com')
            return out
        c.case(f'POST /users {name}', 'POST', '/users', body=body, hdr=hdr, exp_o=eo, exp_r=er, cls=cls,
               reseed=True, post=post)
    U = [
        ('name', {'name': 'Maria Nova'}, 200, 200, None),
        ('email', {'email': 'maria2@email.com'}, 200, 200, None),
        ('email duplicado', {'email': 'joao@email.com'}, (409, 'Email já cadastrado'), (409, 'Email já cadastrado'), None),
        ('email invalido', {'email': 'bad'}, (400, 'Email inválido'), (400, 'Email inválido'), None),
        ('email numero', {'email': 5}, 500, (400, 'Email inválido'), 'C-06'),
        ('email null', {'email': None}, 500, (400, 'Email inválido'), 'C-06'),
        ('password', {'password': '<removido>'}, 200, 200, None),
        ('password curta', {'password': 'abc'}, (400, 'Senha muito curta'), (400, 'Senha muito curta'), None),
        ('password null', {'password': None}, 500, (400, 'Senha inválida'), 'C-06'),
        ('password numero', {'password': 5}, 500, (400, 'Senha inválida'), 'C-06'),
        ('role manager', {'role': 'manager'}, 200, 200, None),
        ('role invalido', {'role': 'xyz'}, (400, 'Role inválido'), (400, 'Role inválido'), None),
        ('active false', {'active': False}, 200, 200, None),
        ('active 0', {'active': 0}, 'medir', (400, 'Campo active inválido'), 'R-07'),
        ('active "x"', {'active': 'x'}, 'medir', (400, 'Campo active inválido'), 'C-06'),
        ('active null', {'active': None}, 'medir', (400, 'Campo active inválido'), 'R-07'),
        ('name null', {'name': None}, 500, (400, 'Nome inválido'), 'C-06'),
        ('name ""', {'name': ''}, 200, (400, 'Nome inválido'), 'R-06'),
        ('name numero', {'name': 5}, 'medir', (400, 'Nome inválido'), 'R-06'),
        ('corpo {}', {}, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo "name"', 'name', 500, (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, er, cls in U:
        c.case(f'PUT /users/2 {name} (admin)', 'PUT', '/users/2', body=body, hdr='A', exp_o=eo, exp_r=er, cls=cls,
               reseed=True, post=get_counts('/users/2'))
    c.case('PUT /users/999 (admin)', 'PUT', '/users/999', body={'name': 'x'}, hdr='A',
           exp=(404, 'Usuário não encontrado'), reseed=True)
    c.case('DELETE /users/3 com 3 tasks (admin)', 'DELETE', '/users/3', hdr='A', exp=200, reseed=True,
           post=lambda cc: {'counts': counts(), 'tasks_user3': q('SELECT COUNT(*) FROM tasks WHERE user_id=3')[0][0],
                            'tasks_outros': q('SELECT COUNT(*) FROM tasks WHERE user_id IN (1,2)')[0][0]})
    c.case('DELETE /users/4 sem tasks (admin)', 'DELETE', '/users/4', hdr='A', exp=200, reseed=True,
           setup=lambda cc: cc.raw('POST', '/users', {'name': 'Sem Tasks', 'email': 'st@email.com', 'password': '<removido>'}),
           post=get_counts())
    c.case('DELETE /users/999 (admin)', 'DELETE', '/users/999', hdr='A', exp=(404, 'Usuário não encontrado'), reseed=True)
    L = [
        ('correto', {'email': 'joao@email.com', 'password': '<removido>'}, 200, 200, None),
        ('senha errada', {'email': 'joao@email.com', 'password': 'errada'}, (401, 'Credenciais inválidas'), (401, 'Credenciais inválidas'), None),
        ('email inexistente', {'email': 'x@email.com', 'password': '<removido>'}, (401, 'Credenciais inválidas'), (401, 'Credenciais inválidas'), None),
        ('campos ausentes', {}, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('sem senha', {'email': 'joao@email.com'}, (400, 'Email e senha são obrigatórios'), (400, 'Email e senha são obrigatórios'), None),
        ('email numero', {'email': 5, 'password': '<removido>'}, 'medir', (401, 'Credenciais inválidas'), 'M-05'),
        ('email true', {'email': True, 'password': '<removido>'}, 'medir', (401, 'Credenciais inválidas'), 'M-05'),
        ('email lista', {'email': ['joao@email.com'], 'password': '<removido>'}, 'medir', (401, 'Credenciais inválidas'), 'C-08'),
        ('email objeto', {'email': {'a': 1}, 'password': '<removido>'}, 'medir', (401, 'Credenciais inválidas'), 'C-08'),
        ('senha numero email existente', {'email': 'joao@email.com', 'password': <removido>}, 500, (401, 'Credenciais inválidas'), 'C-08'),
        ('senha numero email inexistente', {'email': 'x@email.com', 'password': <removido>}, (401, 'Credenciais inválidas'), (401, 'Credenciais inválidas'), None),
        ('corpo null', None, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, er, cls in L:
        c.case(f'POST /login {name}', 'POST', '/login', body=body, exp_o=eo, exp_r=er, cls=cls, reseed=True,
               qc=name.startswith('email '))
    c.case('POST /login inativo', 'POST', '/login', body={'email': 'pedro@email.com', 'password': '<removido>'},
           exp=(403, 'Usuário inativo'), reseed=True,
           setup=lambda cc: q("UPDATE users SET active=0 WHERE email='pedro@email.com'"))


def g_categories_escrita(c):
    P = [
        ('padrao', {'name': 'Nova'}, 201, 201, None),
        ('cor valida', {'name': 'Nova', 'color': '#ABCDEF'}, 201, 201, None),
        ('cor invalida', {'name': 'Nova', 'color': 'red'}, 201, (400, 'Cor inválida'), 'R-09'),
        ('cor null', {'name': 'Nova', 'color': None}, 201, (400, 'Cor inválida'), 'R-09'),
        ('sem nome', {'color': '#ABCDEF'}, (400, 'Nome é obrigatório'), (400, 'Nome é obrigatório'), None),
        ('nome numero', {'name': 5}, 'medir', (400, 'Nome inválido'), 'R-08'),
        ('nome lista', {'name': ['a']}, 'medir', (400, 'Nome inválido'), 'C-10'),
        ('descricao numero', {'name': 'Nova', 'description': 5}, 'medir', (400, 'Descrição inválida'), 'R-08'),
        ('descricao null', {'name': 'Nova', 'description': None}, 201, 201, None),
        ('corpo null', None, (400, 'Dados inválidos'), (400, 'Dados inválidos'), None),
        ('corpo [1]', [1], 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
    ]
    for name, body, eo, er, cls in P:
        c.case(f'POST /categories {name}', 'POST', '/categories', body=body, exp_o=eo, exp_r=er, cls=cls,
               reseed=True, post=get_counts('/categories'))
    U = [
        ('parcial', {'name': 'Ren'}, 200, 200, None),
        ('corpo {}', {}, 200, 200, None),
        ('corpo null', None, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 0', 0, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo false', False, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo 5', 5, 500, (400, 'Dados inválidos'), 'C-01'),
        ('corpo []', [], 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo ""', '', 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo [1]', [1], 200, (400, 'Dados inválidos'), 'R-01'),
        ('corpo "x"', 'x', 200, (400, 'Dados inválidos'), 'R-01'),
        ('nome null', {'name': None}, 500, (400, 'Nome é obrigatório'), 'C-09'),
        ('nome ""', {'name': ''}, 200, (400, 'Nome inválido'), 'R-08'),
        ('nome numero', {'name': 5}, 'medir', (400, 'Nome inválido'), 'R-08'),
        ('cor invalida', {'color': 'bad'}, 200, (400, 'Cor inválida'), 'R-09'),
        ('cor valida', {'color': '#123456'}, 200, 200, None),
    ]
    for name, body, eo, er, cls in U:
        c.case(f'PUT /categories/1 {name}', 'PUT', '/categories/1', body=body, exp_o=eo, exp_r=er, cls=cls,
               reseed=True, post=get_counts('/categories'))
    c.case('PUT /categories/999', 'PUT', '/categories/999', body={'name': 'x'}, exp=(404, 'Categoria não encontrada'), reseed=True)
    c.case('DELETE /categories/1 com tasks', 'DELETE', '/categories/1', exp=200, reseed=True,
           post=lambda cc: {'counts': counts(),
                            'tasks_cat_null': q('SELECT COUNT(*) FROM tasks WHERE category_id IS NULL')[0][0],
                            'tasks_cat_1': q('SELECT COUNT(*) FROM tasks WHERE category_id=1')[0][0]})
    c.case('DELETE /categories/5 sem tasks', 'DELETE', '/categories/5', exp=200, reseed=True,
           setup=lambda cc: cc.raw('POST', '/categories', {'name': 'Vazia'}), post=get_counts())
    c.case('DELETE /categories/999', 'DELETE', '/categories/999', exp=(404, 'Categoria não encontrada'), reseed=True)


def _sign(payload, key=None):
    from itsdangerous import URLSafeTimedSerializer
    tok = URLSafeTimedSerializer(key or os.environ['SECRET_KEY'], salt=SALT).dumps(payload)
    note_secret(tok)
    return tok


def g_auth(c):
    """Controle de acesso. No original serve como evidência de F-04 (tudo aberto)."""
    c.reseed()
    put = {'name': 'Alterado'}
    c.case('auth PUT anonimo', 'PUT', '/users/2', body=put, exp_o=200, exp_r=(401, 'Token ausente'), cls='D-1a', reseed=True)
    c.case('auth DELETE anonimo', 'DELETE', '/users/2', exp_o=200, exp_r=(401, 'Token ausente'), cls='D-1a', reseed=True)
    bad_headers = [
        ('Bearer sem token', 'Bearer'), ('Basic', 'Basic abc'), ('dois espacos', None), ('token vazio', 'Bearer '),
        ('adulterado', None), ('outra chave', None), ('longo demais', 'Bearer ' + 'a' * 5000),
    ]
    for name, h in bad_headers:
        def setup(cc, name=name):
            pass
        c.reseed()
        if name == 'dois espacos':
            h = 'Bearer  ' + (c.tokens['M'] or '')
        if name == 'adulterado':
            t = c.tokens['M'] or 'x'
            h = 'Bearer ' + t[:-2] + ('A' if t[-2] != 'A' else 'B') + t[-1]
        if name == 'outra chave':
            h = 'Bearer ' + _sign({'uid': 2, 'sid': 'a' * 43}, key='outra-chave-de-teste-com-32-caracteres!!')
        c.case(f'auth header {name}', 'PUT', '/users/2', body=put, hdr={'Authorization': h},
               exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a')
    c.reseed()
    c.case('auth bearer minusculo valido', 'PUT', '/users/2', body=put,
           hdr={'Authorization': 'bearer ' + (c.tokens['M'] or '')}, exp=200)
    if not ORIG:
        nonce2 = nonce_of(2)
        payloads = [
            ('uid str', {'uid': '2', 'sid': nonce2}), ('uid bool', {'uid': True, 'sid': nonce2}),
            ('uid 0', {'uid': 0, 'sid': nonce2}), ('uid negativo', {'uid': -1, 'sid': nonce2}),
            ('sem sid', {'uid': 2}), ('sid curto', {'uid': 2, 'sid': 'abc'}),
            ('sid caracteres', {'uid': 2, 'sid': '!' * 43}), ('chave extra', {'uid': 2, 'sid': nonce2, 'x': 1}),
            ('payload lista', [2, nonce2]), ('uid inexistente', {'uid': 999, 'sid': nonce2}),
            ('sid de outro', {'uid': 2, 'sid': nonce_of(1)}),
        ]
        for name, pl in payloads:
            c.case(f'auth payload {name}', 'PUT', '/users/2', body=put,
                   hdr={'Authorization': 'Bearer ' + _sign(pl)}, exp_r=(401, 'Token inválido'), cls='D-1a')
        c.case('auth payload valido assinado pelo harness', 'PUT', '/users/2', body=put,
               hdr={'Authorization': 'Bearer ' + _sign({'uid': 2, 'sid': nonce2})}, exp_r=200)
        # expiração
        import time
        app_exp = make_app({'TOKEN_MAX_AGE': 1})
        cl = app_exp.test_client()
        r = cl.post('/login', json={'email': 'maria@email.com', 'password': '<removido>'})
        tok = r.get_json()['token']
        note_secret(tok)
        time.sleep(2.2)
        r2 = cl.put('/users/2', json=put, headers={'Authorization': 'Bearer ' + tok})
        c.fact('auth token expirado', [r2.status_code, (r2.get_json() or {}).get('error')], exp=[401, 'Token expirado'])
    # matriz
    M = [
        ('proprio altera nome', 'PUT', '/users/2', {'name': 'Maria X'}, 'M', 200, 200, None),
        ('proprio altera email', 'PUT', '/users/2', {'email': 'mx@email.com'}, 'M', 200, 200, None),
        ('proprio altera senha', 'PUT', '/users/2', {'password': '<removido>'}, 'M', 200, 200, None),
        ('outro usuario', 'PUT', '/users/3', {'name': 'X'}, 'M', 200, (403, 'Permissão negada'), 'D-1a'),
        ('proprio role diferente', 'PUT', '/users/2', {'role': 'admin'}, 'M', 200, (403, 'Permissão negada'), 'D-1a'),
        ('proprio role igual', 'PUT', '/users/2', {'role': 'user'}, 'M', 200, 200, None),
        ('proprio active diferente', 'PUT', '/users/2', {'active': False}, 'M', 200, (403, 'Permissão negada'), 'D-1a'),
        ('proprio active igual', 'PUT', '/users/2', {'active': True}, 'M', 200, 200, None),
        ('manager outro', 'PUT', '/users/2', {'name': 'X'}, 'P', 200, (403, 'Permissão negada'), 'D-1a'),
        ('admin outro role', 'PUT', '/users/2', {'role': 'manager'}, 'A', 200, 200, None),
        ('admin outro active', 'PUT', '/users/2', {'active': False}, 'A', 200, 200, None),
        ('delete proprio user', 'DELETE', '/users/2', None, 'M', 200, (403, 'Permissão negada'), 'D-1a'),
        ('delete outro user', 'DELETE', '/users/3', None, 'M', 200, (403, 'Permissão negada'), 'D-1a'),
        ('delete admin outro', 'DELETE', '/users/2', None, 'A', 200, 200, None),
        ('admin rebaixa a si mesmo', 'PUT', '/users/1', {'role': 'user'}, 'A', 200, 200, None),
        ('admin inativa a si mesmo', 'PUT', '/users/1', {'active': False}, 'A', 200, 200, None),
        ('admin exclui a si mesmo (ultimo admin)', 'DELETE', '/users/1', None, 'A', 200, 200, None),
    ]
    for name, m, p, body, who, eo, er, cls in M:
        kw = {} if body is None else {'body': body}
        c.case(f'matriz {name}', m, p, hdr=who, exp_o=eo, exp_r=er, cls=cls, reseed=True, **kw)
    # inativo e reativado
    c.reseed()
    tokP = c.tokens['P']
    c.raw('PUT', '/users/3', {'active': False}, hdr=c.bearer('A'))
    c.case('inativo usa token', 'PUT', '/users/3', body={'name': 'P'}, hdr={'Authorization': f'Bearer {tokP}'},
           exp_o=200, exp_r=(403, 'Usuário inativo'), cls='D-1a')
    c.case('inativo POST /users com bearer', 'POST', '/users',
           body={'name': 'N', 'email': 'n@email.com', 'password': '<removido>'}, hdr={'Authorization': f'Bearer {tokP}'},
           exp_o=201, exp_r=(403, 'Usuário inativo'), cls='D-1a', post=get_counts())
    c.raw('PUT', '/users/3', {'active': True}, hdr=c.bearer('A'))
    c.case('reativado usa token', 'PUT', '/users/3', body={'name': 'P'}, hdr={'Authorization': f'Bearer {tokP}'}, exp=200)
    # rebaixamento vale na hora
    c.reseed()
    tokM = c.tokens['M']
    c.raw('PUT', '/users/2', {'role': 'admin'}, hdr=c.bearer('A'))
    c.case('promovido opera como admin', 'PUT', '/users/3', body={'name': 'P2'}, hdr={'Authorization': f'Bearer {tokM}'}, exp=200)
    c.raw('PUT', '/users/2', {'role': 'user'}, hdr=c.bearer('A'))
    c.case('rebaixado perde admin na hora', 'PUT', '/users/3', body={'name': 'P3'}, hdr={'Authorization': f'Bearer {tokM}'},
           exp_o=200, exp_r=(403, 'Permissão negada'), cls='D-1a')
    # POST /users com bearer expirado/de conta excluída
    c.reseed()
    tokX = c.tokens['P']
    c.raw('DELETE', '/users/3', hdr=c.bearer('A'))
    c.case('POST /users bearer de conta excluida', 'POST', '/users',
           body={'name': 'N', 'email': 'n@email.com', 'password': '<removido>'}, hdr={'Authorization': f'Bearer {tokX}'},
           exp_o=201, exp_r=(401, 'Token inválido'), cls='D-1a', post=get_counts())


def g_ciclo_token(c):
    """Reutilização de ID, novo seed, troca de senha, MD5 legado, hashes malformados."""
    # exclusão + recriação com o mesmo ID
    for variante, y_role, hdr_y in [('Y user', 'user', None), ('Y admin', 'admin', 'A')]:
        c.reseed()
        r = c.raw('POST', '/users', {'name': 'X', 'email': 'x@email.com', 'password': '<removido>'})
        x_id = (r.get('json') or {}).get('id')
        tokX = c.login('x@email.com', '<removido>')
        c.raw('DELETE', f'/users/{x_id}', hdr=c.bearer('A'))
        body = {'name': 'Y', 'email': 'y@email.com', 'password': '<removido>', 'role': y_role}
        r = c.raw('POST', '/users', body, hdr=c.bearer(hdr_y) if hdr_y else None)
        y_id = (r.get('json') or {}).get('id')
        c.fact(f'reuso de ID ({variante}): Y recebeu o mesmo ID de X', y_id == x_id and y_id is not None, exp=True)
        target = '/users/2' if y_role == 'admin' else f'/users/{y_id}'
        method = 'DELETE' if y_role == 'admin' else 'PUT'
        c.case(f'reuso de ID ({variante}): token antigo de X', method, target,
               body=MISSING if method == 'DELETE' else {'name': 'Hackeado'},
               hdr={'Authorization': f'Bearer {tokX}'}, exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a',
               post=lambda cc, yid=y_id: {'y': q('SELECT name, role FROM users WHERE id=?', (yid,)),
                                          'counts': counts()})
        tokY = c.login('y@email.com', '<removido>')
        c.case(f'reuso de ID ({variante}): controle com token novo de Y', 'PUT', f'/users/{y_id}',
               body={'name': 'Y2'}, hdr={'Authorization': f'Bearer {tokY}'}, exp=200)
    # novo seed
    c.reseed()
    tokA = c.tokens['A']
    n_before = nonce_of(1)
    c.reseed(login=False)
    n_after = nonce_of(1)
    c.fact('novo seed: admin mantém id 1', q("SELECT id FROM users WHERE email='joao@email.com'")[0][0], exp=1)
    if not ORIG:
        c.fact('novo seed: nonce do admin mudou', n_before != n_after and n_after is not None, exp=True)
    c.case('novo seed: token antigo do admin', 'PUT', '/users/2', body={'name': 'Z'},
           hdr={'Authorization': f'Bearer {tokA}'}, exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a')
    c.login_all()
    c.case('novo seed: token novo do admin', 'PUT', '/users/2', body={'name': 'Z'}, hdr='A', exp=200)
    # troca de senha pelo próprio usuário
    c.reseed()
    T1 = c.login('maria@email.com', '<removido>')
    T2 = c.login('maria@email.com', '<removido>')
    c.case('senha: troca com T1', 'PUT', '/users/2', body={'password': '<removido>'},
           hdr={'Authorization': f'Bearer {T1}'}, exp=200)
    c.case('senha: T1 depois da troca', 'PUT', '/users/2', body={'name': 'M'},
           hdr={'Authorization': f'Bearer {T1}'}, exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a')
    c.case('senha: T2 depois da troca', 'PUT', '/users/2', body={'name': 'M'},
           hdr={'Authorization': f'Bearer {T2}'}, exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a')
    c.case('senha: login com a antiga', 'POST', '/login', body={'email': 'maria@email.com', 'password': '<removido>'},
           exp=(401, 'Credenciais inválidas'))
    T3 = c.login('maria@email.com', '<removido>')
    c.case('senha: token novo funciona', 'PUT', '/users/2', body={'name': 'M3'},
           hdr={'Authorization': f'Bearer {T3}'}, exp=200)
    # admin troca a senha de outro
    c.reseed()
    tokP = c.tokens['P']
    c.case('senha: admin troca senha de pedro', 'PUT', '/users/3', body={'password': '<removido>'}, hdr='A', exp=200)
    c.case('senha: token antigo de pedro', 'PUT', '/users/3', body={'name': 'P'},
           hdr={'Authorization': f'Bearer {tokP}'}, exp_o=200, exp_r=(401, 'Token inválido'), cls='D-1a')
    c.case('senha: token do admin continua', 'PUT', '/users/2', body={'name': 'M'}, hdr='A', exp=200)
    # troca de senha com commit forçado a falhar
    c.reseed()
    T1 = c.login('maria@email.com', '<removido>')
    before = q('SELECT password FROM users WHERE id=2')[0][0], nonce_of(2)
    from sqlalchemy import event, exc
    from sqlalchemy.orm import Session

    def boom(session, ctx_, inst):
        raise exc.OperationalError('forcado', None, Exception('falha forcada de flush'))
    event.listen(Session, 'before_flush', boom)
    try:
        c.case('senha: commit falha', 'PUT', '/users/2', body={'password': '<removido>'},
               hdr={'Authorization': f'Bearer {T1}'}, exp=(500, 'Erro ao atualizar'))
    finally:
        event.remove(Session, 'before_flush', boom)
    after = q('SELECT password FROM users WHERE id=2')[0][0], nonce_of(2)
    c.fact('senha: commit falho mantém hash e nonce', before == after, exp=True)
    c.case('senha: T1 continua válido após falha', 'PUT', '/users/2', body={'name': 'M'},
           hdr={'Authorization': f'Bearer {T1}'}, exp=200)
    # MD5 legado (D-2a)
    c.reseed()
    q('UPDATE users SET password=? WHERE id=2', (hashlib.md5(b'<removido>').hexdigest(),))
    T0 = c.login('maria@email.com', '<removido>') if not ORIG else None
    n0 = nonce_of(2)
    c.case('md5 legado: login', 'POST', '/login', body={'email': 'maria@email.com', 'password': '<removido>'}, exp=200)
    c.fact('md5 legado: formato do hash após login', hash_kind('maria@email.com'),
           exp='md5' if ORIG else 'werkzeug-scrypt', cls='D-2a')
    if not ORIG:
        c.fact('md5 legado: nonce mantido', nonce_of(2) == n0, exp=True)
        c.case('md5 legado: token anterior continua', 'PUT', '/users/2', body={'name': 'Maria Santos'},
               hdr={'Authorization': f'Bearer {T0}'}, exp=200)
    c.case('md5 legado: login seguinte (formato novo)', 'POST', '/login',
           body={'email': 'maria@email.com', 'password': '<removido>'}, exp=200)
    c.case('md5 legado: senha errada', 'POST', '/login', body={'email': 'maria@email.com', 'password': 'zzzz'},
           exp=(401, 'Credenciais inválidas'))
    # hashes malformados
    md5_1234 = hashlib.md5(b'<removido>').hexdigest()
    for name, h in [('vazio', ''), ('abc', 'abc'), ('werkzeug truncado', 'scrypt:32768:8:1$abc'),
                    ('md5 31', md5_1234[:31]), ('md5 maiusculo', md5_1234.upper())]:
        c.reseed()
        q('UPDATE users SET password=? WHERE id=1', (h,))
        c.case(f'hash malformado {name}', 'POST', '/login', body={'email': 'joao@email.com', 'password': '<removido>'},
               exp=(401, 'Credenciais inválidas'))


def g_rollback(c):
    from sqlalchemy import event, exc
    from sqlalchemy.orm import Session

    def conflict_once(email):
        state = {'done': False}

        def hook(session, ctx_, inst):
            if not state['done']:
                state['done'] = True
                con = sqlite3.connect(DBP)
                cols = columns('users')
                if 'auth_nonce' in cols:
                    con.execute('INSERT INTO users (name,email,password,role,active,auth_nonce,created_at) '
                                'VALUES (?,?,?,?,?,?,?)', ('Corrida', email, 'x' * 32, 'user', 1, 'n' * 43, FIXED_TS))
                else:
                    con.execute('INSERT INTO users (name,email,password,role,active,created_at) VALUES (?,?,?,?,?,?)',
                                ('Corrida', email, 'x' * 32, 'user', 1, FIXED_TS))
                con.commit()
                con.close()
        return hook
    c.reseed()
    h = conflict_once('corrida@email.com')
    event.listen(Session, 'before_flush', h)
    try:
        c.case('conflito forçado POST /users', 'POST', '/users',
               body={'name': 'Conflito', 'email': 'corrida@email.com', 'password': '<removido>'},
               exp_o=(500, 'Erro ao criar usuário'), exp_r=(409, 'Email já cadastrado'), cls='C-07')
    finally:
        event.remove(Session, 'before_flush', h)
    c.case('recuperação da aplicação após conflito', 'GET', '/users', exp=200)
    c.reseed()
    h = conflict_once('corrida2@email.com')
    event.listen(Session, 'before_flush', h)
    try:
        c.case('conflito forçado PUT /users/2', 'PUT', '/users/2', body={'email': 'corrida2@email.com'}, hdr='A',
               exp_o=(500, 'Erro ao atualizar'), exp_r=(409, 'Email já cadastrado'), cls='C-07')
    finally:
        event.remove(Session, 'before_flush', h)
    c.case('recuperação da aplicação após conflito PUT', 'PUT', '/users/2', body={'name': 'Ok'}, hdr='A', exp=200)
    # falha forçada de flush
    c.reseed()
    before = counts()

    def boom(session, ctx_, inst):
        raise exc.OperationalError('forcado', None, Exception('falha forcada de flush'))
    event.listen(Session, 'before_flush', boom)
    try:
        c.case('falha forçada de flush POST /tasks', 'POST', '/tasks', body={'title': 'Falha'},
               exp=(500, 'Erro ao criar task'))
    finally:
        event.remove(Session, 'before_flush', boom)
    c.fact('falha de flush: banco inalterado', counts() == before, exp=True)
    c.case('recuperação da aplicação após falha de flush', 'POST', '/tasks', body={'title': 'Depois'}, exp=201)
    # mesma sessão (só refatorado)
    if not ORIG:
        from database import db, commit_or_rollback
        from errors import ConflictError
        from models.user import User
        c.reseed()
        with c.app.app_context():
            s = db.session()
            u = User(name='Dup', email='joao@email.com', role='user')
            u.set_password('<removido>')
            db.session.add(u)
            got = None
            try:
                commit_or_rollback('Erro ao criar usuário')
            except ConflictError as e:
                got = str(e)
            same = db.session() is s
            active = s.is_active
            u2 = User(name='Valido', email='valido@email.com', role='user')
            u2.set_password('<removido>')
            s.add(u2)
            commit_or_rollback('Erro ao criar usuário')
        persisted = q("SELECT COUNT(*) FROM users WHERE email='valido@email.com'")[0][0]
        c.fact('mesma sessão: ConflictError', got, exp='Email já cadastrado')
        c.fact('mesma sessão: mesmo objeto de sessão', same, exp=True)
        c.fact('mesma sessão: sessão ativa após rollback', active, exp=True)
        c.fact('mesma sessão: commit seguinte persistiu (conexão separada)', persisted, exp=1)


def g_seed_falha(c):
    c.reseed(login=False)
    q("INSERT INTO categories (name, description, color) VALUES ('Marcador','m','#999999')")
    q("INSERT INTO tasks (title, status, priority) VALUES ('Tarefa marcadora','pending',3)")
    before = snapshot()
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
        try:
            with c.app.app_context():
                db.session.remove()
        except Exception:
            pass
    after = snapshot()
    c.fact('seed falha: exceção propagada', err, exp='RuntimeError')
    c.fact('seed falha: snapshot idêntico', snap_digest(before) == snap_digest(after),
           exp=None if ORIG else True, cls='F-06')
    c.fact('seed falha: contagens antes', {k: len(v['rows']) for k, v in before.items()})
    c.fact('seed falha: contagens depois', {k: len(v['rows']) for k, v in after.items()},
           exp=None if ORIG else {k: len(v['rows']) for k, v in before.items()}, cls='F-06')


def g_marcador(c):
    """Popula com seed + marcadores (para testes de CLI do seed)."""
    c.reseed(login=False)
    q("INSERT INTO categories (name, description, color) VALUES ('Marcador','m','#999999')")
    c.fact('snapshot', snap_digest(snapshot(exclude_cols=())))


def g_snapshot(c):
    c.fact('snapshot', snap_digest(snapshot(exclude_cols=())))
    c.fact('counts', counts())


# ---------------------------------------------------------------- migração (refatorado)
def g_migracao(c_unused=None):
    pass


GROUPS = {
    'seed_leitura': g_seed_leitura, 'vazio': g_vazio, 'bordas': g_bordas, 'tasks_escrita': g_tasks_escrita,
    'users_escrita': g_users_escrita, 'categories_escrita': g_categories_escrita, 'auth': g_auth,
    'ciclo_token': g_ciclo_token, 'rollback': g_rollback, 'seed_falha': g_seed_falha,
    'marcador': g_marcador, 'snapshot': g_snapshot,
}


def main():
    ctx = Ctx()
    GROUPS[GROUP](ctx)
    with open(OUT, 'w') as fh:
        json.dump({'mode': MODE, 'group': GROUP, 'records': ctx.records}, fh, ensure_ascii=False, indent=1, default=str)
    bad = [r['name'] for r in ctx.records if r.get('exp_ok') is False]
    print(f'{GROUP}: {len(ctx.records)} registros; expectativas falhas: {len(bad)}', file=sys.__stdout__)
    for b in bad:
        print('  FALHOU:', b, file=sys.__stdout__)


if __name__ == '__main__':
    main()
