"""Reprodução por HTTP das falhas da revisão independente (rodada 2).

Uso: python reproducao.py <dir_app> <saida.txt>
Inicia `python app.py` em <dir_app> com banco isolado, executa os casos e grava
status, corpo e efeito no banco. Token e senhas vêm do ambiente e são mascarados.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

APP_DIR, OUT = sys.argv[1], sys.argv[2]
URL = "http://127.0.0.1:5000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = os.environ["ADMIN_TOKEN"]
SEGREDOS = [TOKEN, os.environ["SEED_SENHA_ADMIN"]]
linhas = []


def mascarar(texto):
    for s in SEGREDOS:
        texto = texto.replace(s, "<removido>")
    return texto


def req(metodo, caminho, bruto=None, token=None):
    headers = {"Content-Type": "application/json"} if bruto is not None else {}
    if token:
        headers["X-Admin-Token"] = token
    r = urllib.request.Request(URL + caminho, data=bruto.encode() if bruto is not None else None,
                               method=metodo, headers=headers)
    try:
        with OPENER.open(r, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


work = tempfile.mkdtemp(prefix="repro-")
db = os.path.join(work, "loja.db")
env = {**os.environ, "DATABASE_PATH": db}
logf = open(os.path.join(work, "server.log"), "w")
proc = subprocess.Popen([sys.executable, "app.py"], cwd=APP_DIR, env=env, stdout=logf, stderr=subprocess.STDOUT)
for _ in range(30):
    try:
        OPENER.open(URL + "/health", timeout=1)
        break
    except OSError:
        time.sleep(0.5)


def dump_produtos():
    return sqlite3.connect(db).execute("SELECT id, nome, preco, estoque FROM produtos ORDER BY id").fetchall()


def caso(nome, metodo, caminho, bruto=None, token=None, efeito=None):
    antes = efeito() if efeito else None
    st, corpo = req(metodo, caminho, bruto, token)
    depois = efeito() if efeito else None
    linha = f"{st} | {nome} | {metodo} {caminho} | entrada: {bruto} | resposta: {corpo.strip()[:160]}"
    if efeito:
        linha += f" | dados alterados: {'SIM' if antes != depois else 'não'}"
        if antes != depois:
            novos = [r for r in depois if r not in antes]
            linha += f" ({novos})"
    linhas.append(mascarar(linha))


linhas.append("## 1. Números não finitos")
corpo = '{{"nome": "Produto X", "preco": {p}, "estoque": {e}, "categoria": "geral"}}'
for rotulo, p, e in [("preco=1e309", "1e309", "1"), ("preco=NaN", "NaN", "1"), ("preco=Infinity", "Infinity", "1"),
                     ("preco=-Infinity", "-Infinity", "1"), ("estoque=1e309", "1", "1e309"), ("estoque=NaN", "1", "NaN")]:
    caso(f"POST /produtos {rotulo}", "POST", "/produtos", corpo.format(p=p, e=e), efeito=dump_produtos)
for rotulo, p, e in [("preco=1e309", "1e309", "1"), ("preco=NaN", "NaN", "1"), ("estoque=Infinity", "1", "Infinity")]:
    caso(f"PUT /produtos/1 {rotulo}", "PUT", "/produtos/1", corpo.format(p=p, e=e), efeito=dump_produtos)
caso("POST /produtos valores válidos (preço decimal, estoque 0)", "POST", "/produtos", corpo.format(p="12.5", e="0"), efeito=dump_produtos)
caso("PUT /produtos/1 valores válidos", "PUT", "/produtos/1", corpo.format(p="5999.99", e="10"), efeito=dump_produtos)
for filtro in ("preco_min=inf", "preco_min=nan", "preco_max=1e309", "preco_max=-inf", "preco_min=100&preco_max=300"):
    caso(f"GET /produtos/busca?{filtro}", "GET", f"/produtos/busca?{filtro}")

linhas.append("")
linhas.append("## 2. Tipo de consulta administrativa")
for bruto in ('{"consulta": ["contagem_por_tabela"]}', '{"consulta": {"nome": "contagem_por_tabela"}}',
              '{"consulta": 1}', '{"consulta": true}', '{"consulta": "contagem_por_tabela"}'):
    caso("POST /admin/query (token correto)", "POST", "/admin/query", bruto, TOKEN)
caso("POST /admin/query lista, sem token", "POST", "/admin/query", '{"consulta": ["contagem_por_tabela"]}')

linhas.append("")
linhas.append("## 3. Senhas legadas e hashes malformados")
legados = [("legado1@loja.com", "abc$def$ghi"), ("legado2@loja.com", "texto-puro"),
           ("legado3@loja.com", "pbkdf2:sha256:abc$salt$hash"), ("legado4@loja.com", "pbkdf2:nada:10$salt$hash"),
           ("legado5@loja.com", "scrypt:x:8:1$salt$hash")]
con = sqlite3.connect(db)
con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Legado', ?, ?, 'cliente')", legados)
con.commit()
con.close()


def dump_usuarios():
    return sqlite3.connect(db).execute("SELECT id, email, senha FROM usuarios ORDER BY id").fetchall()


for email, senha in legados:
    caso(f"POST /login {email} (senha armazenada {senha!r}, informada igual)", "POST", "/login",
         json.dumps({"email": email, "senha": senha}), efeito=dump_usuarios)
caso("POST /login admin com hash válido e senha correta", "POST", "/login",
     json.dumps({"email": "admin@loja.com", "senha": os.environ["SEED_SENHA_ADMIN"]}), efeito=dump_usuarios)
caso("POST /login admin com senha errada", "POST", "/login",
     json.dumps({"email": "admin@loja.com", "senha": "errada"}), efeito=dump_usuarios)

proc.terminate()
proc.wait(timeout=10)
logf.close()
log = open(os.path.join(work, "server.log")).read()
linhas.append("")
linhas.append(f"Tracebacks no log do servidor: {log.count('Traceback')}")
for linha in log.splitlines():
    if linha.startswith(("ValueError", "TypeError", "hashlib.", "_hashlib.")):
        linhas.append("  " + linha)
open(OUT, "w").write("\n".join(linhas) + "\n")
print("\n".join(linhas))
