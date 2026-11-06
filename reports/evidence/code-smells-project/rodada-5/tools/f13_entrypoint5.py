"""F-13 / S1–S9 pelo ponto de entrada real (`python -B app.py`), em bancos novos e temporários.
Rodada 5: token nas rotas protegidas por D-10/D-11 e /health sem "ambiente" (D-9 b); demais asserções iguais.

Uso: python f13_entrypoint.py <dir_projeto> <saida.txt>
ADMIN_TOKEN e SEED_SENHA_* vêm do ambiente (secrets.env) e são SEMPRE passados ao servidor,
inclusive com SEED_ON_STARTUP=0, para provar que é a flag que impede a carga. Segredos mascarados.
"""
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PROJ, OUT = sys.argv[1], sys.argv[2]
PY = sys.executable
URL = "http://127.0.0.1:5000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = os.environ["ADMIN_TOKEN"]
SEEDS = {k: os.environ[k] for k in ("SEED_SENHA_ADMIN", "SEED_SENHA_JOAO", "SEED_SENHA_MARIA")}
EMAIL_VAR = {"admin@loja.com": "SEED_SENHA_ADMIN", "joao@email.com": "SEED_SENHA_JOAO", "maria@email.com": "SEED_SENHA_MARIA"}
TABELAS = ("produtos", "usuarios", "pedidos", "itens_pedido")
WORK = tempfile.mkdtemp(prefix="f13_")
linhas, falhas, segredos = [], [], [TOKEN, *SEEDS.values()]


def mascarar(t):
    for s in segredos:
        t = t.replace(s, "<removido>")
    return t


def log(t=""):
    linhas.append(mascarar(t))


def check(nome, cond, det=""):
    log(("OK   " if cond else "FALHA") + f" {nome}" + (f" — {det}" if det else ""))
    if not cond:
        falhas.append(nome)


def req(metodo, caminho, corpo=None, token=None):
    headers, data = {}, None
    if corpo is not None:
        data, headers["Content-Type"] = json.dumps(corpo).encode(), "application/json"
    if token:
        headers["X-Admin-Token"] = token
    r = urllib.request.Request(URL + caminho, data=data, method=metodo, headers=headers)
    try:
        with OPENER.open(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or "null")


def q(db, sql, p=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, p).fetchall()
    finally:
        con.close()


def tabelas(db):
    return sorted(r[0] for r in q(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


def cont(db):
    return {t: q(db, f"SELECT COUNT(*) FROM {t}")[0][0] for t in TABELAS}


def dump(db):
    return {t: q(db, f"SELECT * FROM {t} ORDER BY id") for t in TABELAS}


class Servidor:
    def __init__(self, nome, db, seed, senhas=None):
        """seed: None = variável ausente; senão o texto exato de SEED_ON_STARTUP."""
        env = {k: v for k, v in os.environ.items() if k != "SEED_ON_STARTUP"}
        env.update({"DATABASE_PATH": db, "ADMIN_TOKEN": TOKEN, **(senhas or SEEDS)})
        if seed is not None:
            env["SEED_ON_STARTUP"] = seed
        self.logfile = os.path.join(WORK, nome + ".log")
        self.proc = subprocess.Popen([PY, "-B", "app.py"], cwd=PROJ, env=env,
                                     stdout=open(self.logfile, "w"), stderr=subprocess.STDOUT)
        for _ in range(60):
            if self.proc.poll() is not None:
                return
            try:
                OPENER.open(URL + "/health", timeout=1)
                return
            except urllib.error.HTTPError:
                return
            except OSError:
                time.sleep(0.25)
        raise RuntimeError(nome + " não iniciou")

    def parar(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)

    def texto(self):
        return open(self.logfile).read()


def novo(nome):
    return os.path.join(WORK, nome + ".db")


ZERO = dict.fromkeys(TABELAS, 0)
DEMO = {"produtos": 10, "usuarios": 3, "pedidos": 0, "itens_pedido": 0}
PRODUTO = {"nome": "Produto Manual", "descricao": "d", "preco": 10.0, "estoque": 5, "categoria": "geral"}

log("Senhas sintéticas de demonstração (SEED_SENHA_*) e ADMIN_TOKEN configuradas em TODAS as execuções.")

# S1 ------------------------------------------------------------------------------------------
log("")
log("## S1 — banco novo, SEED_ON_STARTUP=0")
db = novo("s1")
s = Servidor("s1", db, "0")
check("boot por python app.py", "Rodando em http://127.0.0.1:5000" in s.texto() and s.proc.poll() is None)
check("4 tabelas criadas", tabelas(db) == sorted(TABELAS), str(tabelas(db)))
check("4 tabelas vazias", cont(db) == ZERO, str(cont(db)))
st, js = req("GET", "/produtos")
check("GET /produtos → 200 {'dados': [], 'sucesso': True}", (st, js) == (200, {"dados": [], "sucesso": True}))
st, js = req("GET", "/health")
check("GET /health → 200, contagens zeradas, corpo com as mesmas chaves e valores fixos",
      st == 200 and js == {"status": "ok", "database": "connected", "counts": {"produtos": 0, "usuarios": 0, "pedidos": 0},
                           "versao": "1.0.0", "debug": False}, json.dumps(js))
st, js = req("GET", "/usuarios", token=TOKEN)
check("GET /usuarios (token) → nenhum usuário de demonstração", (st, js) == (200, {"dados": [], "sucesso": True}))
for email, var in EMAIL_VAR.items():
    st, _ = req("POST", "/login", {"email": email, "senha": SEEDS[var]})
    check(f"login {email} com a senha sintética configurada → 401 (a flag impediu a carga)", st == 401, str(st))
st, js = req("POST", "/produtos", PRODUTO, token=TOKEN)
check("POST /produtos → 201 id 1", (st, js["dados"]) == (201, {"id": 1}), str(js))
st, js = req("GET", "/produtos/1")
check("GET /produtos/1 → 200 com o produto gravado", st == 200 and js["dados"]["nome"] == "Produto Manual")
senha_teste = secrets.token_urlsafe(12)
segredos.append(senha_teste)
st, _ = req("POST", "/usuarios", {"nome": "Ana", "email": "ana@loja.com", "senha": senha_teste})
check("POST /usuarios → 201", st == 201)
st, js = req("POST", "/login", {"email": "ana@loja.com", "senha": senha_teste})
check("login do usuário gravado → 200", st == 200 and js["dados"]["email"] == "ana@loja.com")
st, js = req("POST", "/pedidos", {"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 2}]})
check("POST /pedidos → 201", st == 201, str(js))
st, js = req("GET", "/pedidos", token=TOKEN)
check("GET /pedidos → 1 pedido com o item gravado", st == 200 and len(js["dados"]) == 1 and js["dados"][0]["itens"][0]["quantidade"] == 2)
check("efeito no banco (consulta direta)", cont(db) == {"produtos": 1, "usuarios": 1, "pedidos": 1, "itens_pedido": 1}, str(cont(db)))
check("estoque baixado 5 → 3", q(db, "SELECT estoque FROM produtos WHERE id = 1") == [(3,)])
t = s.texto()
check("log: 'carga de demonstração desligada' e nenhum aviso de senha de seed",
      "carga de demonstração desligada" in t and "Senha de seed" not in t)
s.parar()

# S2 ------------------------------------------------------------------------------------------
log("")
log("## S2 — banco populado → reset → reinício com SEED_ON_STARTUP=0")
db = novo("s2")
s = Servidor("s2a", db, None)
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 1}]})
check("preparo: banco populado (seed padrão + 1 pedido)", cont(db) == {"produtos": 10, "usuarios": 3, "pedidos": 1, "itens_pedido": 1}, str(cont(db)))
st, js = req("POST", "/admin/reset-db", token=TOKEN)
check("POST /admin/reset-db (token) → 200", (st, js) == (200, {"mensagem": "Banco de dados resetado", "sucesso": True}))
check("após reset: 4 tabelas vazias", cont(db) == ZERO, str(cont(db)))
s.parar()
for i in (1, 2):
    s = Servidor(f"s2_reinicio{i}", db, "0")
    check(f"reinício {i} com SEED_ON_STARTUP=0: tabelas continuam vazias", cont(db) == ZERO and tabelas(db) == sorted(TABELAS), str(cont(db)))
    st, js = req("GET", "/produtos")
    check(f"reinício {i}: GET /produtos → []", (st, js) == (200, {"dados": [], "sucesso": True}))
    s.parar()

# S3 ------------------------------------------------------------------------------------------
log("")
log("## S3 — banco já populado, boot com SEED_ON_STARTUP=0")
db = novo("s3")
s = Servidor("s3a", db, None)
req("POST", "/pedidos", {"usuario_id": 3, "itens": [{"produto_id": 4, "quantidade": 1}]})
s.parar()
antes = dump(db)
s = Servidor("s3b", db, "0")
s.parar()
check("dump completo idêntico antes e depois do boot", dump(db) == antes)

# S4 / S5 / S6 ---------------------------------------------------------------------------------
for rotulo, valor in (("variável ausente", None), ("SEED_ON_STARTUP=1", "1")):
    log("")
    log(f"## S4/S5 — banco novo, {rotulo}")
    db = novo("s4_" + (valor or "ausente"))
    s = Servidor("s4_" + (valor or "ausente"), db, valor)
    check("carga: 10 produtos, 3 usuários, 0 pedidos", cont(db) == DEMO, str(cont(db)))
    check("senhas gravadas com prefixo de hash", all(r[0].startswith(("scrypt:", "pbkdf2:")) for r in q(db, "SELECT senha FROM usuarios")))
    for email, var in EMAIL_VAR.items():
        st, _ = req("POST", "/login", {"email": email, "senha": SEEDS[var]})
        check(f"login {email} → 200", st == 200)
    s.parar()
    antes = dump(db)
    for j, v in enumerate((None, "1", valor)):
        s = Servidor(f"s5_{valor}_{j}", db, v)
        s.parar()
        check(f"S5 reinício {j + 1} (SEED_ON_STARTUP={v!r}): dump idêntico (ids, chaves, criado_em) — sem duplicação", dump(db) == antes, str(cont(db)))

log("")
log("## S6 — seed ligado: reset + reinício")
db = novo("s6")
s = Servidor("s6a", db, None)
req("POST", "/admin/reset-db", token=TOKEN)
check("após reset: vazio", cont(db) == ZERO)
s.parar()
s = Servidor("s6b", db, None)
check("reinício com seed ligado repõe a demonstração (10/3)", cont(db) == DEMO, str(cont(db)))
s.parar()

# S7 ------------------------------------------------------------------------------------------
log("")
log("## S7 — seed ligado: produtos apagados via API, usuários existentes, reinício com OUTRAS senhas sintéticas")
db = novo("s7")
s = Servidor("s7a", db, None)
for pid in range(1, 11):
    req("DELETE", f"/produtos/{pid}", token=TOKEN)
check("10 produtos apagados via API", cont(db)["produtos"] == 0)
s.parar()
con = sqlite3.connect(db)
con.execute("UPDATE usuarios SET tipo = 'cliente', nome = 'Admin Alterado' WHERE email = 'admin@loja.com'")
con.commit()
con.close()
usuarios_antes = q(db, "SELECT * FROM usuarios ORDER BY id")
outras = {k: secrets.token_urlsafe(12) for k in SEEDS}
segredos.extend(outras.values())
s = Servidor("s7b", db, None, senhas=outras)
check("produtos recarregados (10)", cont(db)["produtos"] == 10)
check("usuários: 3 linhas idênticas (sem duplicar; senha e perfil preservados)", q(db, "SELECT * FROM usuarios ORDER BY id") == usuarios_antes)
st, _ = req("POST", "/login", {"email": "joao@email.com", "senha": SEEDS["SEED_SENHA_JOAO"]})
check("senha original do joao continua valendo → 200", st == 200)
st, _ = req("POST", "/login", {"email": "joao@email.com", "senha": outras["SEED_SENHA_JOAO"]})
check("senha nova do ambiente não substituiu a existente → 401", st == 401)
s.parar()

# S8 ------------------------------------------------------------------------------------------
log("")
log("## S8 — valor inválido impede o boot antes de abrir o banco")
for valor in ("true", "", "2", " 1", "0 ", "false"):
    db = novo("s8_" + str(len(linhas)))
    s = Servidor("s8_" + str(len(linhas)), db, valor)
    try:
        codigo = s.proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        codigo = None
        s.parar()
    t = s.texto()
    check(f"SEED_ON_STARTUP={valor!r}: processo encerra com código 1, mensagem de recusa, banco NÃO criado, porta não aberta",
          codigo == 1 and "Inicialização recusada" in t and "SEED_ON_STARTUP inválido" in t
          and not os.path.exists(db) and "Rodando em" not in t, f"código {codigo}")
primeiro_log = sorted(f for f in os.listdir(WORK) if f.startswith("s8_") and f.endswith(".log"))[0]
recusa = [l for l in open(os.path.join(WORK, primeiro_log)).read().splitlines() if "recusada" in l]
log("trecho do log (primeiro valor inválido): " + (recusa[0].split(" ", 2)[2] if recusa else "(nenhuma linha de recusa no log)"))

# S9 ------------------------------------------------------------------------------------------
log("")
log("## S9 — importar app.py não cria banco nem arquivos")
cwd = tempfile.mkdtemp(prefix="s9_")
antes_proj = sorted(os.listdir(PROJ))
r = subprocess.run([PY, "-I", "-B", "-c", f"import sys; sys.path.insert(0, {PROJ!r}); import app; print(app.__file__)"],
                   cwd=cwd, env={k: v for k, v in os.environ.items() if k not in ("DATABASE_PATH", "SEED_ON_STARTUP")},
                   capture_output=True, text=True, timeout=30)
check("importação: exit 0, app.__file__ correto, cwd vazio, projeto inalterado",
      r.returncode == 0 and r.stdout.strip() == os.path.join(PROJ, "app.py") and os.listdir(cwd) == [] and sorted(os.listdir(PROJ)) == antes_proj,
      f"exit {r.returncode}")
shutil.rmtree(cwd)

log("")
log(f"RESULTADO: {sum(1 for l in linhas if l.startswith('OK'))} OK, {len(falhas)} FALHA(S)")
for f in falhas:
    log("  falhou: " + f)
open(OUT, "w").write("\n".join(linhas) + "\n")
# trecho pertinente dos logs dos servidores, mascarado
with open(os.path.splitext(OUT)[0] + "_logs.txt", "w") as fh:
    for nome in ("s1", "s2_reinicio1", "s7b"):
        fh.write(f"--- {nome}.log (trechos)\n")
        for l in open(os.path.join(WORK, nome + ".log")).read().splitlines():
            if any(k in l for k in ("WARNING", "ERROR", "seed", "demonstração", "Rodando", "Traceback")):
                fh.write(mascarar(l) + "\n")
shutil.rmtree(WORK)
print("\n".join(linhas[-2 - len(falhas):]))
sys.exit(1 if falhas else 0)
