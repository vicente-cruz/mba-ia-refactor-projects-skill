"""Testes específicos das decisões D-1..D-6, rollback, banco legado e erro inesperado.
Rodada 5: token nas operações protegidas por D-10/D-11 (grupos 2 e 5), grupo 7 conforme D-4R (d)+(ii)
e grupo 9 (D-10/D-11 e D-9 b por HTTP real). Demais grupos sem alteração.

Uso: python specific.py <dir_refatorado> <dir_original> <saida.txt>
Segredos vêm do ambiente (secrets.env) e são mascarados na saída.
"""
import importlib.util
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

REFAT, ORIG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
WORK = os.path.join(os.path.dirname(OUT), "specific_work")
PY = sys.executable
URL = "http://127.0.0.1:5000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = os.environ["ADMIN_TOKEN"]
SEEDS = {k: os.environ[k] for k in ("SEED_SENHA_ADMIN", "SEED_SENHA_JOAO", "SEED_SENHA_MARIA")}
SENHA_TESTE = secrets.token_urlsafe(12)  # senha do usuário criado no teste, gerada a cada execução
SEGREDOS = [TOKEN, os.environ["SECRET_KEY"], *SEEDS.values(), SENHA_TESTE]
linhas = []
falhas = []


def mascarar(texto):
    for s in SEGREDOS:
        texto = texto.replace(s, "<removido>")
    return re.sub(r"(scrypt|pbkdf2)[:$][^\"\s']+", "<hash-removido>", texto)


def log(texto=""):
    linhas.append(mascarar(texto))


def check(nome, condicao, detalhe=""):
    log(("OK   " if condicao else "FALHA") + f" {nome}" + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


def req(metodo, caminho, corpo=None, token=None, bruto=None):
    headers = {}
    data = None
    if corpo is not None:
        data, headers["Content-Type"] = json.dumps(corpo).encode(), "application/json"
    if bruto is not None:
        data, headers["Content-Type"] = bruto.encode(), "text/plain"
    if token is not None:
        headers["X-Admin-Token"] = token
    r = urllib.request.Request(URL + caminho, data=data, method=metodo, headers=headers)
    try:
        with OPENER.open(r, timeout=10) as resp:
            status, texto = resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, texto = err.code, err.read().decode()
    try:
        return status, json.loads(texto), texto
    except ValueError:
        return status, None, texto


def q(db, sql, params=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def contagens(db):
    return {t: q(db, f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("produtos", "usuarios", "pedidos", "itens_pedido")}


class Servidor:
    def __init__(self, nome, db, env_extra, cwd=REFAT, comando=None):
        self.nome, self.db = nome, db
        env = {k: v for k, v in os.environ.items()
               if k not in ("ADMIN_TOKEN", "SEED_SENHA_ADMIN", "SEED_SENHA_JOAO", "SEED_SENHA_MARIA")}
        env.update({"DATABASE_PATH": db, **env_extra})
        self.logfile = os.path.join(WORK, f"{nome}.log")
        self.proc = subprocess.Popen(comando or [PY, "app.py"], cwd=cwd, env=env,
                                     stdout=open(self.logfile, "w"), stderr=subprocess.STDOUT)
        for _ in range(30):
            try:
                OPENER.open(URL + "/health", timeout=1)
                return
            except urllib.error.HTTPError:
                return
            except OSError:
                time.sleep(0.5)
        raise RuntimeError(f"{nome} não iniciou")

    def parar(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)

    def log_texto(self):
        return open(self.logfile).read()


def env_completo():
    return {"ADMIN_TOKEN": TOKEN, **SEEDS}


shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
PROTEGIDOS = [("GET", "/usuarios", None), ("GET", "/usuarios/1", None), ("GET", "/relatorios/vendas", None),
              ("POST", "/admin/query", {"consulta": "contagem_por_tabela"}), ("POST", "/admin/reset-db", None)]

# ---------------------------------------------------------------- 1. D-6/D-1/D-2: autorização
log("## 1. Autorização nos 5 endpoints protegidos (D-1 c, D-2 b, D-6 b)")
db = os.path.join(WORK, "auth_sem_token.db")
srv = Servidor("auth_sem_token", db, {k: v for k, v in env_completo().items() if k != "ADMIN_TOKEN"})
antes = contagens(db)
for metodo, caminho, corpo in PROTEGIDOS:
    for rotulo, tok in (("sem header", None), ("com header qualquer", "x")):
        st, js, _ = req(metodo, caminho, corpo, tok)
        check(f"ADMIN_TOKEN não configurado, {rotulo}: {metodo} {caminho} → 403", st == 403 and js == {"erro": "Operação administrativa desabilitada"}, f"{st} {js}")
check("sem ADMIN_TOKEN: contagens inalteradas", contagens(db) == antes, str(contagens(db)))
srv.parar()

db = os.path.join(WORK, "auth.db")
srv = Servidor("auth", db, env_completo())
antes = contagens(db)
for metodo, caminho, corpo in PROTEGIDOS:
    for rotulo, tok in (("sem header", None), ("token incorreto", "token-incorreto"), ("token com prefixo correto", TOKEN[:-1])):
        st, js, _ = req(metodo, caminho, corpo, tok)
        check(f"{rotulo}: {metodo} {caminho} → 401", st == 401 and js == {"erro": "Não autorizado"}, f"{st} {js}")
check("chamadas não autorizadas: contagens inalteradas", contagens(db) == antes, str(contagens(db)))
for metodo, caminho, corpo in PROTEGIDOS[:4]:
    st, js, texto = req(metodo, caminho, corpo, TOKEN)
    check(f"token correto: {metodo} {caminho} → 200", st == 200 and js["sucesso"] is True, f"{st}")
    check(f"  resposta sem senha/hash: {caminho}", '"senha"' not in texto and "scrypt:" not in texto and "pbkdf2:" not in texto)
st, js, _ = req("GET", "/usuarios", None, TOKEN)
check("GET /usuarios autorizado lista os 3 usuários do seed sem campo senha",
      [u["email"] for u in js["dados"]] == ["admin@loja.com", "joao@email.com", "maria@email.com"] and all("senha" not in u for u in js["dados"]))
st, js, _ = req("GET", "/usuarios/999", None, TOKEN)
check("GET /usuarios/999 autorizado → 404 'Usuário não encontrado'", st == 404 and js == {"erro": "Usuário não encontrado"})
st, js, _ = req("GET", "/produtos")
check("endpoint público continua sem token: GET /produtos → 200", st == 200)

# ---------------------------------------------------------------- 2. D-1 (c): consultas predefinidas
log("")
log("## 2. POST /admin/query com consultas predefinidas (D-1 c)")
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 2}]})
req("POST", "/pedidos", {"usuario_id": 3, "itens": [{"produto_id": 6, "quantidade": 5}]})
req("PUT", "/pedidos/1/status", {"status": "aprovado"}, TOKEN)  # rodada 5: D-11 a
esperado = {
    "contagem_por_tabela": [{"tabela": t, "quantidade": n} for t, n in contagens(db).items()],
    "pedidos_por_status": [{"status": s, "quantidade": n, "total": t} for s, n, t in
                           q(db, "SELECT status, COUNT(*), SUM(total) FROM pedidos GROUP BY status ORDER BY status")],
    "usuarios_por_tipo": [{"tipo": t, "quantidade": n} for t, n in
                          q(db, "SELECT tipo, COUNT(*) FROM usuarios GROUP BY tipo ORDER BY tipo")],
}
for nome, dados_esperados in esperado.items():
    st, js, _ = req("POST", "/admin/query", {"consulta": nome}, TOKEN)
    check(f"{nome} → 200 e igual à consulta direta no banco isolado", st == 200 and js["dados"] == dados_esperados, json.dumps(js["dados"], ensure_ascii=False))
for limite in (0, 3, 5, 1000):
    st, js, _ = req("POST", "/admin/query", {"consulta": "produtos_estoque_baixo", "parametros": {"limite": limite}}, TOKEN)
    direto = [{"id": i, "nome": n, "estoque": e} for i, n, e in
              q(db, "SELECT id, nome, estoque FROM produtos WHERE estoque <= ? ORDER BY id", (limite,))]
    check(f"produtos_estoque_baixo limite={limite} → 200, {len(direto)} linha(s), igual à consulta direta", st == 200 and js["dados"] == direto)
st, js, _ = req("POST", "/admin/query", {"consulta": "produtos_estoque_baixo"}, TOKEN)
check("produtos_estoque_baixo sem parâmetros usa limite padrão 5",
      st == 200 and js["dados"] == [{"id": i, "nome": n, "estoque": e} for i, n, e in q(db, "SELECT id, nome, estoque FROM produtos WHERE estoque <= 5 ORDER BY id")])
antes = contagens(db)
for corpo in ({"sql": "DELETE FROM produtos"}, {"sql": "SELECT * FROM usuarios"},
              {"sql": "DROP TABLE usuarios", "consulta": "contagem_por_tabela"}):
    st, js, texto = req("POST", "/admin/query", corpo, TOKEN)
    check(f"corpo {json.dumps(corpo)} → 400 sem execução", st == 400 and js == {"erro": "Execução de SQL arbitrário não é suportada; informe 'consulta'"} and "senha" not in texto, f"{st} {js}")
check("após tentativas de SQL arbitrário: contagens inalteradas e tabela usuarios existe",
      contagens(db) == antes, str(contagens(db)))
casos_400 = [
    ({"consulta": "usuarios_com_senha"}, "Consulta inválida. Válidas: ['contagem_por_tabela', 'pedidos_por_status', 'produtos_estoque_baixo', 'usuarios_por_tipo']"),
    ({"consulta": ["contagem_por_tabela"]}, "Consulta inválida. Válidas: ['contagem_por_tabela', 'pedidos_por_status', 'produtos_estoque_baixo', 'usuarios_por_tipo']"),
    ({"consulta": {"nome": "contagem_por_tabela"}}, "Consulta inválida. Válidas: ['contagem_por_tabela', 'pedidos_por_status', 'produtos_estoque_baixo', 'usuarios_por_tipo']"),
    ({"consulta": "produtos_estoque_baixo", "parametros": {"limite": "5; DROP TABLE produtos"}}, None),
    ({"consulta": "produtos_estoque_baixo", "parametros": {"limite": -1}}, None),
    ({"consulta": "produtos_estoque_baixo", "parametros": {"limite": True}}, None),
    ({"consulta": "produtos_estoque_baixo", "parametros": {"limite": "abc"}}, None),
    ({"consulta": "contagem_por_tabela", "parametros": {"tabela": "usuarios"}}, None),
    ({"consulta": "contagem_por_tabela", "parametros": "x"}, None),
    ({}, "Consulta não informada"),
]
for corpo, msg in casos_400:
    st, js, _ = req("POST", "/admin/query", corpo, TOKEN)
    check(f"{json.dumps(corpo, ensure_ascii=False)} → 400", st == 400 and (msg is None or js["erro"] == msg), f"{st} {js}")
st, js, _ = req("POST", "/admin/query", None, TOKEN, bruto="x")
check("corpo não-JSON → 400 'Dados inválidos'", st == 400 and js == {"erro": "Dados inválidos"})
check("após parâmetros maliciosos: contagens inalteradas", contagens(db) == antes)
srv.parar()
log_auth = srv.log_texto()
check("token não aparece no log do servidor", TOKEN not in log_auth)
check("nenhum traceback no log desta instância", "Traceback" not in log_auth)

# ---------------------------------------------------------------- 3. D-2 (b): reset protegido
log("")
log("## 3. POST /admin/reset-db protegido (D-2 b)")
db = os.path.join(WORK, "reset.db")
srv = Servidor("reset", db, env_completo())
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
c0 = contagens(db)
log(f"preparo (seed + 1 pedido): {c0}")
for rotulo, tok in (("sem header", None), ("header incorreto", "errado")):
    st, js, _ = req("POST", "/admin/reset-db", token=tok)
    check(f"{rotulo} → 401 e contagens iguais", st == 401 and contagens(db) == c0, f"{st} {contagens(db)}")
st, js, _ = req("POST", "/admin/reset-db", token=TOKEN)
check("token correto → 200 com corpo da linha de base", st == 200 and js == {"mensagem": "Banco de dados resetado", "sucesso": True}, f"{st} {js}")
c1 = contagens(db)
check("após reset: 4 tabelas com 0 linhas (consulta direta)", all(v == 0 for v in c1.values()), str(c1))
st, js, _ = req("GET", "/produtos")
check("GET /produtos após reset → {'dados': [], 'sucesso': True}", js == {"dados": [], "sucesso": True})
st, js, _ = req("GET", "/health")
check("GET /health após reset → contagens zeradas", js["counts"] == {"produtos": 0, "usuarios": 0, "pedidos": 0})
check("reset registrado como WARNING no log", "WARNING" in srv.log_texto() and "resetado" in srv.log_texto())
srv.parar()
srv = Servidor("reset_reinicio", db, env_completo())
c2 = contagens(db)
check("reinício sobre o mesmo banco repete o seed (10 produtos, 3 usuários)", c2 == {"produtos": 10, "usuarios": 3, "pedidos": 0, "itens_pedido": 0}, str(c2))
srv.parar()
con = sqlite3.connect(db)
con.execute("CREATE TRIGGER falha_reset BEFORE DELETE ON usuarios BEGIN SELECT RAISE(ABORT, 'falha forcada'); END")
con.commit()
con.close()
srv = Servidor("reset_falha", db, env_completo())
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
c3 = contagens(db)
st, js, _ = req("POST", "/admin/reset-db", token=TOKEN)
check("falha forçada no DELETE de usuarios → 500 genérico", st == 500 and js == {"erro": "Erro interno do servidor"}, f"{st} {js}")
check("rollback: nenhuma tabela esvaziada", contagens(db) == c3, f"antes {c3} depois {contagens(db)}")
check("erro inesperado registrado no log com traceback", "Erro não tratado" in srv.log_texto() and "Traceback" in srv.log_texto())
srv.parar()

# ---------------------------------------------------------------- 4. D-3 (d): seed por configuração
log("")
log("## 4. Seed com senhas por configuração (D-3 d)")
db = os.path.join(WORK, "seed.db")
srv = Servidor("seed", db, env_completo())
usuarios_seed = [("admin@loja.com", "SEED_SENHA_ADMIN", {"id": 1, "nome": "Admin", "email": "admin@loja.com", "tipo": "admin"}),
                 ("joao@email.com", "SEED_SENHA_JOAO", {"id": 2, "nome": "João Silva", "email": "joao@email.com", "tipo": "cliente"}),
                 ("maria@email.com", "SEED_SENHA_MARIA", {"id": 3, "nome": "Maria Santos", "email": "maria@email.com", "tipo": "cliente"})]
for email, var, esperado_dados in usuarios_seed:
    st, js, _ = req("POST", "/login", {"email": email, "senha": SEEDS[var]})
    check(f"login {email} com senha configurada → 200 e dados da linha de base", st == 200 and js == {"dados": esperado_dados, "sucesso": True, "mensagem": "Login OK"}, f"{st}")
    st, js, _ = req("POST", "/login", {"email": email, "senha": "senha-errada"})
    check(f"login {email} com senha errada → 401", st == 401 and js == {"erro": "Email ou senha inválidos", "sucesso": False})
for email, senha in q(db, "SELECT email, senha FROM usuarios ORDER BY id"):
    plano = SEEDS[dict((e, v) for e, v, _ in usuarios_seed)[email]]
    check(f"banco: senha de {email} com prefixo de hash e diferente da configurada", senha.startswith(("scrypt:", "pbkdf2:")) and senha != plano)
st, js, _ = req("POST", "/usuarios", {"nome": "Novo", "email": "novo@loja.com", "senha": SENHA_TESTE})
novo = q(db, "SELECT senha FROM usuarios WHERE email = 'novo@loja.com'")[0][0]
check("POST /usuarios grava senha com hash", st == 201 and novo.startswith(("scrypt:", "pbkdf2:")))
st, js, _ = req("POST", "/login", {"email": "admin@loja.com' --", "senha": "x"})
check("login com injeção → 401", st == 401)
srv.parar()

db = os.path.join(WORK, "seed_sem_vars.db")
srv = Servidor("seed_sem_vars", db, {"ADMIN_TOKEN": TOKEN})
st, js, _ = req("GET", "/usuarios", token=TOKEN)
check("sem SEED_SENHA_*: nenhum usuário de demonstração criado", st == 200 and js["dados"] == [], f"{js}")
check("sem SEED_SENHA_*: produtos do seed criados normalmente", contagens(db)["produtos"] == 10)
st, js, _ = req("POST", "/login", {"email": "admin@loja.com", "senha": SEEDS["SEED_SENHA_ADMIN"]})
check("sem SEED_SENHA_*: login do admin → 401", st == 401)
texto_log = srv.log_texto()
check("sem SEED_SENHA_*: aviso no log para os 3 e-mails",
      all(f"não configurada para {e}" in texto_log for e, _, _ in usuarios_seed))
check("log da inicialização não contém nenhuma senha de seed", all(s not in texto_log for s in SEEDS.values()))
srv.parar()

db = os.path.join(WORK, "seed_parcial.db")
srv = Servidor("seed_parcial", db, {"ADMIN_TOKEN": TOKEN, "SEED_SENHA_JOAO": SEEDS["SEED_SENHA_JOAO"]})
st, js, _ = req("GET", "/usuarios", token=TOKEN)
check("só SEED_SENHA_JOAO definida: apenas joao@email.com criado", [u["email"] for u in js["dados"]] == ["joao@email.com"])
srv.parar()

db = os.path.join(WORK, "sem_secret.db")
srv = Servidor("sem_secret", db, {**env_completo(), "SECRET_KEY": ""})
st, js, _ = req("GET", "/health")
check("sem SECRET_KEY: aplicação inicia (health 200) com aviso de chave efêmera no log",
      st == 200 and "SECRET_KEY não definida" in srv.log_texto() and "secret_key" not in json.dumps(js), f"{st}")
srv.parar()

# ---------------------------------------------------------------- 5. Rollback do pedido (F-09)
log("")
log("## 5. Rollback na criação de pedido (F-09)")
db = os.path.join(WORK, "rollback.db")
srv = Servidor("rollback", db, env_completo())
srv.parar()
con = sqlite3.connect(db)
con.execute("CREATE TRIGGER falha_item BEFORE INSERT ON itens_pedido WHEN NEW.produto_id = 3 BEGIN SELECT RAISE(ABORT, 'falha forcada'); END")
con.commit()
con.close()
srv = Servidor("rollback2", db, env_completo())
antes = (contagens(db), q(db, "SELECT estoque FROM produtos WHERE id = 2")[0][0])
st, js, _ = req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 2}, {"produto_id": 3, "quantidade": 1}]})
check("falha na 2ª inserção de item → 500 genérico (sem str(e))", st == 500 and js == {"erro": "Erro interno do servidor"}, f"{st} {js}")
st, _, _ = req("POST", "/produtos", {"nome": "Produto Independente", "preco": 1, "estoque": 1, "categoria": "geral"}, TOKEN)  # rodada 5: D-11 a
depois = (contagens(db), q(db, "SELECT estoque FROM produtos WHERE id = 2")[0][0])
check("escrita independente posterior → 201", st == 201)
check("nenhum pedido/item parcial e estoque do produto 2 intacto após escrita independente",
      depois[0]["pedidos"] == antes[0]["pedidos"] and depois[0]["itens_pedido"] == antes[0]["itens_pedido"] and depois[1] == antes[1],
      f"antes {antes} depois {depois}")
srv.parar()

db = os.path.join(WORK, "estoque.db")
srv = Servidor("estoque", db, env_completo())
st, js, _ = req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 6, "quantidade": 5}, {"produto_id": 6, "quantidade": 5}]})
check("itens repetidos que somados excedem o estoque (8) → 400 e estoque intacto",
      st == 400 and js == {"erro": "Estoque insuficiente para Cadeira Gamer", "sucesso": False}
      and q(db, "SELECT estoque FROM produtos WHERE id = 6")[0][0] == 8 and contagens(db)["pedidos"] == 0, f"{st} {js}")
for corpo in ({"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 0}]},
              {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1.5}]},
              {"usuario_id": 2, "itens": [{"produto_id": 1}]},
              {"usuario_id": "2", "itens": [{"produto_id": 1, "quantidade": 1}]},
              {"usuario_id": 2, "itens": {"produto_id": 1}}):
    st, js, _ = req("POST", "/pedidos", corpo)
    check(f"pedido inválido {json.dumps(corpo)} → 400", st == 400, f"{st} {js}")

# ---------------------------------------------------------------- 6. Relatório: faixas de desconto
log("")
log("## 6. Relatório de vendas: faixas de desconto (comparação com o código original)")
srv.parar()
sys.path.insert(0, ORIG)
import models as models_original  # noqa: E402  (código original, só a função de relatório)
import database as database_original  # noqa: E402
sys.path.pop(0)
_spec = importlib.util.spec_from_file_location("relatorio_refat", os.path.join(REFAT, "models", "relatorio.py"))
relatorio_refat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relatorio_refat)
for faturamento in (0, 999.99, 1000, 1000.01, 5000, 5000.01, 10000, 10000.01, 25000):
    alvo = os.path.join(WORK, f"rel_{faturamento}.db")
    shutil.copy(os.path.join(WORK, "estoque.db"), alvo)
    con = sqlite3.connect(alvo)
    con.execute("DELETE FROM pedidos")
    if faturamento:
        con.execute("INSERT INTO pedidos (usuario_id, status, total) VALUES (1, 'aprovado', ?)", (faturamento,))
        con.execute("INSERT INTO pedidos (usuario_id, status, total) VALUES (1, 'cancelado', 0)")
    con.commit()
    con.close()
    database_original.db_connection = None
    database_original.db_path = alvo
    original = models_original.relatorio_vendas()
    database_original.db_connection.close()
    con = sqlite3.connect(alvo)
    con.row_factory = sqlite3.Row
    novo = relatorio_refat.vendas(con)
    con.close()
    check(f"faturamento {faturamento}: relatório refatorado == original", novo == original, json.dumps(novo))

# ---------------------------------------------------------------- 7. D-4R (d)+(ii): banco legado
log("")
log("## 7. Banco legado com senhas em texto puro (D-4R d + ii; substitui o grupo D-4 a)")
legado = os.path.join(WORK, "legado.db")
orig = Servidor("legado_original", legado, {}, cwd=WORK,
                comando=[PY, "-c", f"import sys; sys.path.insert(0, {ORIG!r}); import database; database.db_path = {legado!r}; database.get_db(); import app; app.app.run(host='127.0.0.1', port=5000)"])
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
st, js, _ = req("POST", "/usuarios", {"nome": "Legado Cifrao", "email": "cifrao@loja.com", "senha": "abc$def$ghi"})
orig.parar()
def dump_legado():
    return (q(legado, "SELECT * FROM produtos") + q(legado, "SELECT * FROM pedidos") + q(legado, "SELECT * FROM itens_pedido")
            + q(legado, "SELECT id, nome, email, senha, tipo, criado_em FROM usuarios"))
dump_antes = dump_legado()
senhas_legadas = dict(q(legado, "SELECT email, senha FROM usuarios"))
env = {k: v for k, v in os.environ.items() if k not in ("ADMIN_TOKEN", "SEED_SENHA_ADMIN", "SEED_SENHA_JOAO", "SEED_SENHA_MARIA")}
env.update({"DATABASE_PATH": legado, **env_completo()})
r = subprocess.run([PY, "app.py"], cwd=REFAT, env=env, capture_output=True, text=True, timeout=60)
check("refatorado sobre banco legado: boot recusado (código 1) com instrução de migração",
      r.returncode == 1 and "Inicialização recusada" in r.stderr + r.stdout and "migrar_senhas.py" in r.stderr + r.stdout, f"código {r.returncode}")
check("boot recusado: dump idêntico (nada alterado, sem seed)", dump_legado() == dump_antes)
r = subprocess.run([PY, "migrar_senhas.py", legado, "--aplicar"], cwd=REFAT, capture_output=True, text=True, timeout=60)
check("migrar_senhas.py --aplicar → código 0, 4 credenciais invalidadas", r.returncode == 0 and "4 credencial(is) invalidada(s)" in r.stdout, f"código {r.returncode}")
dump_depois = dump_legado()
check("após a migração: produtos, pedidos e itens idênticos; usuários com mesmos ids/nomes/e-mails/perfis e senha NULL",
      dump_depois[:-4] == dump_antes[:-4] and [u[:3] + u[4:] for u in dump_depois[-4:]] == [u[:3] + u[4:] for u in dump_antes[-4:]]
      and all(u[3] is None for u in dump_depois[-4:]))
srv = Servidor("legado_refatorado", legado, env_completo())
st, js, _ = req("POST", "/login", {"email": "admin@loja.com", "senha": senhas_legadas["admin@loja.com"]})
check("após a migração: login com a senha legada → 401", st == 401 and js == {"erro": "Email ou senha inválidos", "sucesso": False}, f"{st}")
st, js, _ = req("POST", "/login", {"email": "cifrao@loja.com", "senha": "abc$def$ghi"})
check("conta legada criada pelo original com senha 'abc$def$ghi' → 401 (rodada 1: 500)", st == 401 and js == {"erro": "Email ou senha inválidos", "sucesso": False}, f"{st} {js}")
st, js, _ = req("GET", "/pedidos", token=TOKEN)
check("banco migrado: dados existentes continuam legíveis (GET /pedidos com token → 1 pedido)", st == 200 and len(js["dados"]) == 1)
srv.parar()
check("login legado não gerou traceback no log", "Traceback" not in srv.log_texto())
check("banco migrado: inicialização e uso não alteraram os dados", dump_legado() == dump_depois)

# ---------------------------------------------------------------- 8. Erros gerais e rotas inexistentes
log("")
log("## 8. Erros gerais")
db = os.path.join(WORK, "erros.db")
srv = Servidor("erros", db, env_completo())
st, _, texto = req("GET", "/rota-inexistente")
check("rota inexistente → 404 HTML padrão do Flask (preservado)", st == 404 and "<!doctype html>" in texto.lower())
st, _, texto = req("PATCH", "/produtos")
check("método não permitido → 405 (preservado)", st == 405)
st, _, _ = req("GET", "/produtos/abc")
check("id não numérico → 404 do conversor <int:> (preservado)", st == 404)
con = sqlite3.connect(db)
con.execute("ALTER TABLE produtos RENAME TO produtos_x")
con.commit()
con.close()
st, js, texto = req("GET", "/produtos")
check("erro de banco inesperado → 500 {'erro': 'Erro interno do servidor'} sem detalhes SQL", st == 500 and js == {"erro": "Erro interno do servidor"} and "no such table" not in texto)
st, js, _ = req("GET", "/health")
check("health com banco quebrado → 500 {'status': 'erro', ...} sem detalhes internos", st == 500 and js["status"] == "erro" and "no such" not in json.dumps(js), json.dumps(js, ensure_ascii=False))
check("detalhe do erro fica apenas no log", "no such table" in srv.log_texto())
srv.parar()

# ---------------------------------------------------------------- 9. D-10/D-11 e D-9 por HTTP real
log("")
log("## 9. Rotas protegidas por D-10 (a) / D-11 (a) e /health sem ambiente (D-9 b)")
NOVOS = [("GET", "/pedidos", None, 200), ("GET", "/pedidos/usuario/2", None, 200),
         ("PUT", "/pedidos/1/status", {"status": "enviado"}, 200),
         ("POST", "/produtos", {"nome": "Novo", "preco": 1, "estoque": 1, "categoria": "geral"}, 201),
         ("PUT", "/produtos/1", {"nome": "Preco zero", "preco": 0, "estoque": 1, "categoria": "geral"}, 200),
         ("DELETE", "/produtos/2", None, 200)]
def dump_db(db):
    return [q(db, f"SELECT * FROM {t} ORDER BY id") for t in ("produtos", "usuarios", "pedidos", "itens_pedido")]
db = os.path.join(WORK, "d10_sem_token.db")
srv = Servidor("d10_sem_token", db, {k: v for k, v in env_completo().items() if k != "ADMIN_TOKEN"})
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
antes = dump_db(db)
for metodo, caminho, corpo, _ in NOVOS:
    for rotulo, tok in (("sem header", None), ("com header qualquer", "x")):
        st, js, _ = req(metodo, caminho, corpo, tok)
        check(f"ADMIN_TOKEN não configurado, {rotulo}: {metodo} {caminho} → 403", st == 403 and js == {"erro": "Operação administrativa desabilitada"}, f"{st} {js}")
check("sem ADMIN_TOKEN: dados idênticos (dump das 4 tabelas)", dump_db(db) == antes)
srv.parar()
db = os.path.join(WORK, "d10.db")
srv = Servidor("d10", db, env_completo())
req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
antes = dump_db(db)
for metodo, caminho, corpo, _ in NOVOS:
    for rotulo, tok in (("sem header", None), ("token incorreto", "token-incorreto"), ("token com prefixo correto", TOKEN[:-1])):
        st, js, _ = req(metodo, caminho, corpo, tok)
        check(f"{rotulo}: {metodo} {caminho} → 401", st == 401 and js == {"erro": "Não autorizado"}, f"{st} {js}")
check("chamadas não autorizadas: dados idênticos (dump das 4 tabelas)", dump_db(db) == antes)
for metodo, caminho, corpo, esperado in NOVOS:
    st, js, _ = req(metodo, caminho, corpo, TOKEN)
    check(f"token correto: {metodo} {caminho} → {esperado}", st == esperado and js["sucesso"] is True, f"{st}")
check("token correto: efeitos gravados (status enviado, preço 0, produto 2 removido, produto 11 criado)",
      q(db, "SELECT status FROM pedidos WHERE id = 1") == [("enviado",)]
      and q(db, "SELECT preco FROM produtos WHERE id = 1") == [(0.0,)]
      and q(db, "SELECT COUNT(*) FROM produtos WHERE id = 2") == [(0,)]
      and q(db, "SELECT nome FROM produtos WHERE id = 11") == [("Novo",)])
st, js, texto = req("GET", "/health")
check("GET /health: sem 'ambiente'; campos status, database, counts, versao e debug",
      st == 200 and sorted(js) == ["counts", "database", "debug", "status", "versao"], json.dumps(js, ensure_ascii=False))
check("GET /health: sem token, SECRET_KEY, senhas, hash nem caminho do banco",
      all(s not in texto for s in SEGREDOS) and db not in texto and WORK not in texto and "scrypt" not in texto)
st, js, _ = req("POST", "/pedidos", {"usuario_id": 2, "itens": [{"produto_id": 3, "quantidade": 1}]})
check("POST /pedidos continua público → 201", st == 201)
srv.parar()

log("")
log(f"RESULTADO: {sum(1 for l in linhas if l.startswith('OK'))} OK, {len(falhas)} FALHA(S)")
for f in falhas:
    log(f"  falhou: {f}")
open(OUT, "w").write("\n".join(linhas) + "\n")
print("\n".join(linhas[-3 - len(falhas):]))
