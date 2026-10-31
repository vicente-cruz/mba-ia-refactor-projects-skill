"""Reprodução por HTTP: login de contas cuja coluna senha tem hash malformado (rodada 3).

Uso: python reproducao_hashes.py <dir_app> <saida.txt>
Inicia `python app.py` em <dir_app> com banco isolado, insere as contas direto no banco,
tenta o login e registra status, corpo, alteração do banco e exceções no log.
A senha do admin vem de SEED_SENHA_ADMIN (mascarada na saída).
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
SENHA_ADMIN = os.environ["SEED_SENHA_ADMIN"]
CASOS = [
    ("revisao1@loja.com", "pbkdf2:sha256:1000$salt$á"),
    ("revisao2@loja.com", "pbkdf2:sha256:999999999999999999999$salt$hash"),
    ("revisao3@loja.com", "scrypt:32768:8:-1$salt$hash"),
    ("extra1@loja.com", "scrypt:9999999999:9999999999:9999999999$salt$00"),
    ("extra2@loja.com", "scrypt:3:8:1$salt$00"),
    ("extra3@loja.com", "pbkdf2:sha256:0$salt$00"),
    ("extra4@loja.com", "pbkdf2:sha256:1000$salt$ÿ"),
]

work = tempfile.mkdtemp(prefix="repro3-")
db = os.path.join(work, "loja.db")
logf = open(os.path.join(work, "server.log"), "w")
proc = subprocess.Popen([sys.executable, "-B", "app.py"], cwd=APP_DIR, env={**os.environ, "DATABASE_PATH": db},
                        stdout=logf, stderr=subprocess.STDOUT)
for _ in range(30):
    try:
        OPENER.open(URL + "/health", timeout=1)
        break
    except OSError:
        time.sleep(0.5)

con = sqlite3.connect(db)
con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Malformado', ?, ?, 'cliente')", CASOS)
con.commit()
con.close()


def usuarios():
    return sqlite3.connect(db).execute("SELECT id, nome, email, senha, tipo, criado_em FROM usuarios ORDER BY id").fetchall()


def login(email, senha):
    r = urllib.request.Request(URL + "/login", data=json.dumps({"email": email, "senha": senha}).encode(),
                               method="POST", headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


linhas = []
for email, armazenado in CASOS + [("admin@loja.com", None)]:
    for senha in ([SENHA_ADMIN, "errada"] if armazenado is None else ["qualquer-senha"]):
        antes = usuarios()
        t = time.time()
        st, corpo = login(email, senha)
        alterou = usuarios() != antes
        rotulo = f"armazenado {armazenado!r}" if armazenado else ("hash válido, senha correta" if senha != "errada" else "hash válido, senha errada")
        linhas.append(f"{st} | {email} ({rotulo}) | {corpo.strip()} | banco alterado: {'SIM' if alterou else 'não'} | {time.time() - t:.2f}s")

proc.terminate()
proc.wait(timeout=10)
logf.close()
log = open(os.path.join(work, "server.log")).read()
linhas.append("")
linhas.append(f"Tracebacks no log do servidor: {log.count('Traceback')}")
linhas += ["  " + l for l in log.splitlines() if l.startswith(("TypeError", "ValueError", "OverflowError", "_hashlib.", "hashlib."))]
linhas.append(f"Avisos de formato inválido no log: {log.count('formato inválido ou não suportado')}")
texto = "\n".join(linhas).replace(SENHA_ADMIN, "<removido>") + "\n"
open(OUT, "w").write(texto)
print(texto)
