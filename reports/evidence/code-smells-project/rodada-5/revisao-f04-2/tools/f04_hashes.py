"""F-04, revisão 2 da rodada 5: preservação de hashes válidos do Werkzeug na migração.

Uso: python -B f04_hashes.py <dir_projeto> <saida.txt>

Hashes válidos gerados por generate_password_hash e aceitos por _senha_confere:
  pbkdf2:sha512_256:600000, pbkdf2:sha512_224:600000 e scrypt com salt_length=129
(e, como referência, scrypt e pbkdf2:sha256 padrão). Os critérios são os do comportamento corrigido;
sobre o código anterior à correção, o roteiro registra as falhas reproduzidas (controle "antes").
Bancos temporários, senhas sintéticas mascaradas.
"""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile

PROJ, SAIDA = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, PROJ)
import database  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

PY = sys.executable
WORK = tempfile.mkdtemp(prefix="f04hash_")
linhas, falhas = [], []
SENHAS = {}
MARCA = "LEGADO-" + secrets.token_hex(8)
GIGANTE = "scrypt:" + "9" * 4400 + ":8:1$s$" + "a" * 128
CASOS = [  # (e-mail, método, kwargs, perfil)
    ("sha512_256@x", "pbkdf2:sha512_256:600000", {}, "admin"),
    ("sha512_224@x", "pbkdf2:sha512_224:600000", {}, "cliente"),
    ("scrypt_salt129@x", "scrypt", {"salt_length": 129}, "cliente"),
    ("scrypt_padrao@x", "scrypt", {}, "cliente"),
    ("pbkdf2_padrao@x", "pbkdf2", {}, "admin"),
]
HASHES = {}
for email, metodo, kwargs, _ in CASOS:
    SENHAS[email] = "SENHA-" + secrets.token_hex(8)
    HASHES[email] = generate_password_hash(SENHAS[email], method=metodo, **kwargs)


def mascarar(texto):
    for email, senha in SENHAS.items():
        texto = texto.replace(senha, "<senha>").replace(HASHES[email], "<hash-removido>")
    return texto.replace(MARCA, "<marca>").replace(GIGANTE, "<scrypt-gigante>").replace(WORK, "<tmp>")


def log(texto=""):
    linhas.append(mascarar(texto))
    print(mascarar(texto), flush=True)


def check(nome, condicao, detalhe=""):
    log(("OK   " if condicao else "FALHA") + " " + nome + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


def estado(pasta):
    resultado = {}
    for nome in sorted(os.listdir(pasta)):
        with open(os.path.join(pasta, nome), "rb") as fh:
            resultado[nome] = hashlib.sha256(fh.read()).hexdigest()
    return resultado


def dump(db):
    con = sqlite3.connect(db)
    try:
        return {t: con.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()
                for t in ("produtos", "usuarios", "pedidos", "itens_pedido")}
    finally:
        con.close()


def criar(db, legados):
    con = sqlite3.connect(db)
    for comando in database.SCHEMA:
        con.execute(comando)
    con.executemany("INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)",
                    database.PRODUTOS_SEED)
    for email, _, _, perfil in CASOS:
        con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Hash', ?, ?, ?)", (email, HASHES[email], perfil))
    for i, senha in enumerate(legados):
        con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Legado', ?, ?, 'cliente')", (f"legado{i}@x", senha))
    con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Sem credencial', 'nulo@x', NULL, 'cliente')")
    con.execute("INSERT INTO pedidos (usuario_id, status, total) VALUES (1, 'aprovado', 89.9)")
    con.execute("INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (1, 2, 1, 89.9)")
    con.commit()
    con.close()


def cli(db, *args):
    r = subprocess.run([PY, "-B", "migrar_senhas.py", db, *args], cwd=PROJ, capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


BOOT = """
import json, sys
sys.path.insert(0, ".")
from app import create_app
import database
try:
    app = create_app({"DATABASE_PATH": sys.argv[1], "TESTING": True, "SEED_ON_STARTUP": False})
except database.MigracaoPendenteError as erro:
    print(json.dumps({"boot": "recusado", "motivo": str(erro)}))
    sys.exit(0)
c = app.test_client()
logins = {e: c.post("/login", json={"email": e, "senha": s}).status_code for e, s in json.loads(sys.argv[2]).items()}
print(json.dumps({"boot": "aceito", "logins": logins}))
"""


def boot(db, credenciais):
    r = subprocess.run([PY, "-B", "-c", BOOT, db, json.dumps(credenciais)], cwd=PROJ, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"boot": "erro", "motivo": ("Traceback " if "Traceback" in r.stderr else "") + r.stderr.strip()[-200:]}


def classificacao():
    log("## 0. Classificação direta (models.usuario)")
    codigo = ("import json, sys; sys.path.insert(0, '.'); from models import usuario; h = json.loads(sys.argv[1]); "
              "print(json.dumps({e: [usuario._senha_confere(v, s), usuario.hash_preservavel(v)] for e, (v, s) in h.items()}))")
    entrada = {e: (HASHES[e], SENHAS[e]) for e, *_ in CASOS}
    r = subprocess.run([PY, "-B", "-c", codigo, json.dumps(entrada)], cwd=PROJ, capture_output=True, text=True, timeout=60)
    resultado = json.loads(r.stdout)
    for email, metodo, kwargs, _ in CASOS:
        confere, preserva = resultado[email]
        check(f"{metodo} {kwargs or ''}: aceito por _senha_confere e preservado pela migração",
              confere and preserva, f"_senha_confere={confere} hash_preservavel={preserva}")
    log()


def so_hashes():
    log("## 1. Banco só com hashes válidos (+ 1 conta sem credencial)")
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    criar(db, [])
    antes, dados = estado(pasta), dump(db)
    r = boot(db, SENHAS)
    check("boot aceito", r.get("boot") == "aceito", r.get("motivo", "")[:200])
    check("login de cada conta com hash → 200", r.get("logins") == {e: 200 for e in SENHAS}, str(r.get("logins")))
    check("boot não alterou os dados", dump(db) == dados)
    antes = estado(pasta)
    codigo, saida = cli(db)
    log("simulação: código " + str(codigo) + " | " + saida.replace("\n", " | ")[:300])
    check("simulação: código 0, legadas=0, hashes_validos=5", codigo == 0 and "legadas=0" in saida and "hashes_validos=5" in saida)
    check("simulação: arquivos e conteúdo (sha256) intactos", estado(pasta) == antes)
    log()


def misto():
    log("## 2. Banco misto: hashes válidos + texto puro + texto gigante + conta sem credencial")
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    criar(db, [MARCA, GIGANTE])
    dados = dump(db)
    r = boot(db, SENHAS)
    check("boot recusado (2 credenciais legadas)", r.get("boot") == "recusado" and "2 credencial(is)" in r.get("motivo", ""),
          r.get("motivo", "")[:160])
    antes = estado(pasta)
    codigo, saida = cli(db)
    log("simulação: código " + str(codigo) + " | " + saida.replace("\n", " | ")[:300])
    check("simulação: legadas=2 e hashes_validos=5; arquivos intactos",
          codigo == 0 and "legadas=2" in saida and "hashes_validos=5" in saida and estado(pasta) == antes)
    codigo, saida = cli(db, "--aplicar")
    log("aplicar: código " + str(codigo) + " | " + saida.replace("\n", " | ")[:400])
    depois = dump(db)
    check("--aplicar: código 0 e exatamente 2 credenciais invalidadas", codigo == 0 and "2 credencial(is) invalidada(s)" in saida)
    senhas = {row[2]: row[3] for row in depois["usuarios"]}
    check("--aplicar: os 5 hashes válidos idênticos byte a byte", all(senhas[e] == HASHES[e] for e in HASHES),
          str([e for e in HASHES if senhas[e] != HASHES[e]]))
    check("--aplicar: só as credenciais legadas viraram NULL", senhas["legado0@x"] is None and senhas["legado1@x"] is None
          and senhas["nulo@x"] is None)
    esperado = [row[:3] + ((None,) if row[2].startswith("legado") else (row[3],)) + row[4:] for row in dados["usuarios"]]
    check("--aplicar: IDs, nomes, e-mails, perfis e datas preservados", depois["usuarios"] == esperado)
    check("--aplicar: produtos, pedidos e itens idênticos",
          all(depois[t] == dados[t] for t in ("produtos", "pedidos", "itens_pedido")))
    ocorr = 0
    for nome in os.listdir(pasta):
        with open(os.path.join(pasta, nome), "rb") as fh:
            conteudo = fh.read()
        ocorr += conteudo.count(MARCA.encode()) + conteudo.count(b"9" * 1000)
    check("--aplicar: texto puro e trecho do texto gigante ausentes dos arquivos", ocorr == 0)
    r = boot(db, dict(SENHAS, **{"legado0@x": MARCA}))
    esperado_logins = dict({e: 200 for e in SENHAS}, **{"legado0@x": 401})
    check("após --aplicar: boot aceito; contas com hash → 200; conta legada → 401",
          r.get("boot") == "aceito" and r.get("logins") == esperado_logins, str(r)[:300])
    codigo, saida = cli(db)
    check("segunda simulação: legadas=0, hashes_validos=5", codigo == 0 and "legadas=0" in saida and "hashes_validos=5" in saida)
    log()


try:
    log(f"# F-04 — preservação de hashes válidos — projeto: {os.path.basename(PROJ)}")
    log(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}")
    log()
    for caso in (classificacao, so_hashes, misto):
        try:
            caso()
        except Exception as erro:
            check(f"{caso.__name__}: execução sem exceção no roteiro", False, repr(erro)[:300])
    log(f"Resultado: {'APROVADO' if not falhas else 'REPROVADO'} — {len(falhas)} falha(s)")
finally:
    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if falhas else 0)
