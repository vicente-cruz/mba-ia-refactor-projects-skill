"""F-04, revisão da rodada 5: WAL, simulação somente leitura e texto legado arbitrário.

Uso: python -B f04_wal.py <dir_projeto> <saida.txt>

Os critérios são os do comportamento corrigido. Executado sobre o código anterior à correção,
o roteiro registra as falhas reproduzidas (controle "antes"); sobre o código corrigido, o
controle "depois". Bancos temporários; senhas sintéticas rastreáveis mascaradas como <marca-…>.
"""
import hashlib
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile

PROJ, SAIDA = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, PROJ)
import database  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

PY = sys.executable
WORK = tempfile.mkdtemp(prefix="f04wal_")
MARCAS = {}
linhas, falhas = [], []
SENHA_OK = "SENHA-" + secrets.token_hex(8)
HASH_OK = generate_password_hash(SENHA_OK)
GIGANTE = "scrypt:" + "9" * 4400 + ":8:1$s$" + "a" * 128


def marca(rotulo):
    MARCAS[rotulo] = f"LEGADO-{rotulo}-{secrets.token_hex(8)}"
    return MARCAS[rotulo]


def mascarar(texto):
    for rotulo, valor in MARCAS.items():
        texto = texto.replace(valor, f"<marca-{rotulo}>")
    texto = texto.replace(SENHA_OK, "<senha-ok>").replace(GIGANTE, "<scrypt-gigante>")
    return texto.replace(WORK, "<tmp>")


def log(texto=""):
    linhas.append(mascarar(texto))
    print(mascarar(texto), flush=True)


def check(nome, condicao, detalhe=""):
    log(("OK   " if condicao else "FALHA") + " " + nome + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


def arquivos(pasta):
    return sorted(os.listdir(pasta))


def estado_arquivos(pasta):
    resultado = {}
    for nome in arquivos(pasta):
        with open(os.path.join(pasta, nome), "rb") as fh:
            resultado[nome] = hashlib.sha256(fh.read()).hexdigest()
    return resultado


def ocorrencias(pasta, valor):
    resultado = {}
    for nome in arquivos(pasta):
        with open(os.path.join(pasta, nome), "rb") as fh:
            resultado[nome] = fh.read().count(valor.encode())
    return resultado


def ultima(saida):
    return saida.strip().splitlines()[-1][:220] if saida.strip() else ""


def cli(db, *args):
    r = subprocess.run([PY, "-B", "migrar_senhas.py", db, *args], cwd=PROJ, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


BOOT = """
import sys
sys.path.insert(0, ".")
from app import create_app
import database
try:
    app = create_app({"DATABASE_PATH": sys.argv[1], "TESTING": True, "SEED_ON_STARTUP": False})
except database.MigracaoPendenteError as erro:
    print("RECUSADO:", erro)
    sys.exit(3)
c = app.test_client()
r = c.post("/login", json={"email": "hash@x", "senha": sys.argv[2]})
print("ACEITO; login hash@x ->", r.status_code)
"""


def boot(db):
    r = subprocess.run([PY, "-B", "-c", BOOT, db, SENHA_OK], cwd=PROJ, capture_output=True, text=True, timeout=120)
    if r.returncode == 3:
        return "recusado", ultima(r.stdout)
    if r.returncode == 0 and "ACEITO" in r.stdout:
        return "aceito", ultima(r.stdout)
    return "erro", ("Traceback " if "Traceback" in r.stderr else "") + ultima(r.stderr)


def criar(db, wal, legados, autocheckpoint=True):
    con = sqlite3.connect(db)
    if wal:
        con.execute("PRAGMA journal_mode = WAL")
        if not autocheckpoint:
            con.execute("PRAGMA wal_autocheckpoint = 0")
    for comando in database.SCHEMA:
        con.execute(comando)
    con.executemany("INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)",
                    database.PRODUTOS_SEED)
    con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Hash', 'hash@x', ?, 'admin')", (HASH_OK,))
    for i, senha in enumerate(legados):
        con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Legado', ?, ?, 'cliente')",
                    (f"legado{i}@x", senha))
    con.commit()
    return con


FILHO = r"""
import sqlite3, sys
sys.path.insert(0, ".")
import database
modo, db, hash_ok, *senhas = sys.argv[1:]
con = sqlite3.connect(db, isolation_level=None)
con.execute("PRAGMA journal_mode = WAL")
con.execute("PRAGMA wal_autocheckpoint = 0")
con.execute("BEGIN")
for comando in database.SCHEMA:
    con.execute(comando)
con.executemany("INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)", database.PRODUTOS_SEED)
con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Hash', 'hash@x', ?, 'admin')", (hash_ok,))
con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Legado', 'legado0@x', ?, 'cliente')", (senhas[0],))
con.execute("COMMIT")
if modo == "leitor":
    # Outra conexão com BEGIN e leitura efetiva de usuarios; a conexão de escrita é fechada.
    leitor = sqlite3.connect(db, isolation_level=None)
    leitor.execute("BEGIN")
    n = len(leitor.execute("SELECT id, senha FROM usuarios").fetchall())
    con.close()
    print("PRONTO leitor", n, flush=True)
    sys.stdin.readline()
    leitor.execute("ROLLBACK")
    leitor.close()
else:
    # Escritor: checkpoint, depois um commit que fica só no WAL; a conexão continua aberta.
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Novo', 'novo@x', ?, 'cliente')", (senhas[1],))
    n = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    print("PRONTO escritor", n, flush=True)
    sys.stdin.readline()
    con.close()
"""


class Filho:
    """Conexões mantidas em OUTRO processo: no POSIX, fechar qualquer descritor de um arquivo libera
    todos os locks fcntl do processo sobre ele, o que desfaria o leitor se as leituras de bytes deste
    roteiro acontecessem no mesmo processo."""

    def __init__(self, modo, db, *senhas):
        self.proc = subprocess.Popen([PY, "-B", "-c", FILHO, modo, db, HASH_OK, *senhas], cwd=PROJ,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.pronto = self.proc.stdout.readline().strip()

    def encerrar(self):
        self.proc.stdin.write("\n")
        self.proc.stdin.flush()
        self.proc.wait(30)


def usuarios(db):
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT id, nome, email, senha, tipo FROM usuarios ORDER BY id").fetchall(), \
            con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------
def caso_wal_leitor():
    log("## 1. WAL com leitor aberto (outro processo: BEGIN + SELECT em usuarios) durante --aplicar")
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    m = marca("WAL")
    filho = Filho("leitor", db, m)
    log(f"preparo: {filho.pronto} linha(s); arquivos={arquivos(pasta)}; ocorrências da marca: {ocorrencias(pasta, m)}")
    check("preparo: a marca está nos bytes de loja.db-wal", ocorrencias(pasta, m).get("loja.db-wal", 0) > 0)
    codigo, saida = cli(db, "--aplicar")
    log("aplicar (leitor aberto): código " + str(codigo) + " | " + " | ".join(saida.strip().splitlines())[:700])
    occ = ocorrencias(pasta, m)
    rows, versao = usuarios(db)
    resultado, detalhe = boot(db)
    log(f"após a 1ª execução: arquivos={arquivos(pasta)}; ocorrências={occ}; user_version={versao}; boot={resultado} ({detalhe})")
    check("leitor aberto: a CLI devolve falha controlada (código 1, sem traceback) e orienta o operador",
          codigo == 1 and "Traceback" not in saida and "--aplicar" in saida, f"código {codigo}")
    check("leitor aberto: estado retomável — credencial legada já NULL e limpeza marcada como pendente",
          [r[3] for r in rows if r[2] == "legado0@x"] == [None] and versao == 0x53454E48, f"user_version={versao}")
    check("leitor aberto: boot recusado enquanto a limpeza não for comprovada", resultado == "recusado", detalhe)
    filho.encerrar()
    log(f"leitor fechado: arquivos={arquivos(pasta)}")
    codigo, saida = cli(db, "--aplicar")
    log("retomada (leitor fechado): código " + str(codigo) + " | " + " | ".join(saida.strip().splitlines())[:700])
    occ = ocorrencias(pasta, m)
    rows, versao = usuarios(db)
    check("retomada: código 0", codigo == 0, ultima(saida))
    check("retomada: 0 ocorrências da senha no .db e nos auxiliares presentes", sum(occ.values()) == 0, str(occ))
    check("retomada: hash válido preservado byte a byte e credencial legada NULL; user_version = 0",
          [r[3] for r in rows if r[2] == "hash@x"] == [HASH_OK] and [r[3] for r in rows if r[2] == "legado0@x"] == [None]
          and versao == 0)
    resultado, detalhe = boot(db)
    check("retomada: boot aceito e login da conta com hash → 200", resultado == "aceito" and "200" in detalhe, detalhe)
    log()


def caso_simulacao_wal_fechado():
    log("## 2. Simulação: banco WAL fechado, sem arquivos auxiliares")
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    criar(db, True, [marca("FECHADO")]).close()
    with open(db, "rb") as fh:
        modo = fh.read(20)[18]
    antes = estado_arquivos(pasta)
    log(f"preparo: arquivos={list(antes)}; byte 18 do cabeçalho = {modo} (2 = WAL)")
    codigo, saida = cli(db)
    depois = estado_arquivos(pasta)
    log("simulação: código " + str(codigo) + " | " + " | ".join(saida.strip().splitlines())[:400])
    log(f"arquivos depois: {list(depois)}")
    check("WAL fechado: lista de arquivos e conteúdo (sha256) idênticos antes/depois", depois == antes,
          f"antes={list(antes)} depois={list(depois)}")
    check("WAL fechado: simulação com código 0 e contagem correta (legadas=1)",
          codigo == 0 and "legadas=1" in saida and "Traceback" not in saida, ultima(saida))
    log()


def caso_simulacao_wal_confirmado():
    log("## 3. Simulação: dados confirmados ainda no WAL (escritor aberto em outro processo)")
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    filho = Filho("escritor", db, marca("NO-DB"), marca("SO-NO-WAL"))
    esperado = int(filho.pronto.split()[-1])
    occ = ocorrencias(pasta, MARCAS["SO-NO-WAL"])
    antes = estado_arquivos(pasta)
    log(f"preparo: arquivos={list(antes)}; usuarios confirmados={esperado}; marca nova: {occ}")
    check("preparo: a marca nova está só no WAL", occ.get("loja.db", 0) == 0 and occ.get("loja.db-wal", 0) > 0)
    codigo, saida = cli(db)
    depois = estado_arquivos(pasta)
    log("simulação: código " + str(codigo) + " | " + " | ".join(saida.strip().splitlines())[:400])
    check("dados no WAL: lista de arquivos e conteúdo (sha256 de .db, -wal e -shm) idênticos antes/depois",
          depois == antes, f"mudaram: {sorted(n for n in set(antes) | set(depois) if antes.get(n) != depois.get(n))}")
    check(f"dados no WAL: a simulação considera o confirmado mais recente (usuarios={esperado}, legadas=2)",
          codigo == 0 and f"usuarios={esperado}" in saida and "legadas=2" in saida, ultima(saida))
    filho.encerrar()
    log()


def caso_scrypt_gigante():
    log('## 4. Texto legado arbitrário: "scrypt:" + "9"*4400 + ":8:1$s$" + "a"*128')
    pasta = tempfile.mkdtemp(dir=WORK)
    db = os.path.join(pasta, "loja.db")
    criar(db, False, [GIGANTE]).close()
    sha = estado_arquivos(pasta)
    log(f"preparo: arquivos={list(sha)}; trecho de 1000 '9' presente: {ocorrencias(pasta, '9' * 1000)}")
    resultado, detalhe = boot(db)
    check("boot: recusa controlada (MigracaoPendenteError), sem exceção não tratada", resultado == "recusado", detalhe)
    porta = socket.socket()
    porta.bind(("127.0.0.1", 0))
    numero = porta.getsockname()[1]
    porta.close()
    env = dict(os.environ, DATABASE_PATH=db, PORT=str(numero), ADMIN_TOKEN=secrets.token_hex(8))
    try:
        r = subprocess.run([PY, "-B", "app.py"], cwd=PROJ, env=env, capture_output=True, text=True, timeout=15)
        codigo_app, saida_app = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        codigo_app, saida_app = "servidor iniciou", ""
    check("python app.py: código 1 com 'Inicialização recusada' e sem traceback",
          codigo_app == 1 and "Inicialização recusada" in saida_app and "Traceback" not in saida_app,
          f"código {codigo_app}; {ultima(saida_app)[:160]}")
    check("boot recusado sem alterar o banco", estado_arquivos(pasta) == sha)
    codigo, saida = cli(db)
    log("simulação: código " + str(codigo) + " | " + ultima(saida)[:300])
    check("simulação: código 0 e a credencial é contada (legadas=1)", codigo == 0 and "legadas=1" in saida
          and "Traceback" not in saida, ultima(saida))
    codigo, saida = cli(db, "--aplicar")
    rows, versao = usuarios(db)
    check("--aplicar: código 0, credencial invalidada (NULL), hash válido preservado",
          codigo == 0 and [r[3] for r in rows if r[2] == "legado0@x"] == [None]
          and [r[3] for r in rows if r[2] == "hash@x"] == [HASH_OK] and versao == 0, ultima(saida))
    # O valor (> 4 KiB) fica dividido em páginas de overflow: busca-se um trecho de 1000 caracteres.
    check("--aplicar: o texto gigante não aparece mais no arquivo (trecho de 1000 '9')",
          sum(ocorrencias(pasta, "9" * 1000).values()) == 0)
    resultado, detalhe = boot(db)
    check("após --aplicar: boot aceito e login da conta com hash → 200", resultado == "aceito" and "200" in detalhe, detalhe)
    log()


try:
    log(f"# F-04 — WAL, simulação somente leitura e texto legado arbitrário — projeto: {os.path.basename(PROJ)}")
    log(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}")
    log()
    for caso in (caso_wal_leitor, caso_simulacao_wal_fechado, caso_simulacao_wal_confirmado, caso_scrypt_gigante):
        try:
            caso()
        except Exception as erro:  # registra e segue para os demais casos
            check(f"{caso.__name__}: execução do caso sem exceção no roteiro", False, repr(erro)[:300])
    log(f"Resultado: {'APROVADO' if not falhas else 'REPROVADO'} — {len(falhas)} falha(s)")
finally:
    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if falhas else 0)
