"""F-04 (D-4R d + ii): bancos gerados pelo código ORIGINAL, recusa do boot e migrar_senhas.py (rodada 5).

Uso: python -B f04_migracao.py <dir_refatorado> <dir_original_40d2986> <saida.txt>

Cenários: "legado" (só contas do código original, texto puro) e "misto" (legado + hashes válidos +
conta sem credencial). Cada senha legada é sintética e rastreável (LEGADO-<hex>), gerada por
execução e mascarada na saída. Uma das contas teve a senha trocada com secure_delete OFF, para deixar
a senha antiga como sobra em espaço livre do arquivo (simula um build do SQLite sem secure_delete).
Todos os processos rodam com `python -B` sobre cópias temporárias.
"""
import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REFAT, ORIG, SAIDA = (os.path.abspath(a) for a in sys.argv[1:4])
PY = sys.executable
TOKEN = secrets.token_urlsafe(16)
SEGREDOS = {"<token>": TOKEN, "<secret-key>": secrets.token_hex(32)}
MARCAS = {}  # rótulo -> valor
linhas, falhas = [], []
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SEED_ORIGINAL = ["admin123", "senha123"]  # senhas públicas do seed original ("123456" é curta e ambígua)


def marca(rotulo):
    MARCAS[rotulo] = f"LEGADO-{rotulo}-{secrets.token_hex(8)}"
    return MARCAS[rotulo]


def mascarar(texto):
    for rotulo, valor in MARCAS.items():
        texto = texto.replace(valor, f"<marca-{rotulo}>")
    for rotulo, valor in SEGREDOS.items():
        texto = texto.replace(valor, rotulo)
    return texto.replace(WORK, "<tmp>")


def log(texto=""):
    linhas.append(mascarar(texto))
    print(mascarar(texto), flush=True)


def check(nome, condicao, detalhe=""):
    log(("OK   " if condicao else "FALHA") + " " + nome + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


def sha(caminho):
    with open(caminho, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def arquivos(pasta):
    return sorted(os.listdir(pasta))


def busca_bytes(pasta, valores):
    """Ocorrências de cada valor nos bytes de TODOS os arquivos da pasta (banco, journal, WAL, SHM)."""
    resultado = {}
    for nome in arquivos(pasta):
        with open(os.path.join(pasta, nome), "rb") as fh:
            conteudo = fh.read()
        for valor in valores:
            resultado[(nome, valor)] = conteudo.count(valor.encode())
    return resultado


def total_ocorrencias(pasta, valores):
    return sum(busca_bytes(pasta, valores).values())


def q(db, sql, params=()):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def dump(db):
    tabelas = ("produtos", "usuarios", "pedidos", "itens_pedido", "sqlite_sequence")
    return {t: q(db, f"SELECT * FROM {t} ORDER BY rowid") for t in tabelas}


def env_base(db, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SEED_", "ADMIN_", "DATABASE_"))}
    env.update({"DATABASE_PATH": db, "ADMIN_TOKEN": TOKEN, "SECRET_KEY": SEGREDOS["<secret-key>"],
                "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra)
    return env


def rodar(args, env=None, cwd=REFAT):
    r = subprocess.run([PY, "-B", *args], cwd=cwd, env=env or env_base(""), capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def gerar_legado(pasta, misto):
    """Banco criado e populado pelo código original (40d2986)."""
    db = os.path.join(pasta, "loja.db")
    a_antiga, b, c = marca("A-antiga"), marca("B"), marca("C-excluida")
    codigo = (
        f"import sys; sys.path.insert(0, {ORIG!r}); import database; database.db_path = {db!r}; "
        "database.get_db(); import models; "
        f"models.criar_usuario('Legado A', 'a@legado', {a_antiga!r}); "
        f"models.criar_usuario('Legado B', 'b@legado', {b!r}, 'admin'); "
        f"[models.criar_usuario('Excluida', 'x%d@legado' % i, {c!r} + '-' + 'p' * 200) for i in range(60)]; "
        "print(models.criar_pedido(2, [{'produto_id': 1, 'quantidade': 2}, {'produto_id': 3, 'quantidade': 1}])); "
        "print(models.criar_pedido(4, [{'produto_id': 2, 'quantidade': 1}]))"
    )
    codigo_saida, saida = rodar(["-c", codigo], cwd=pasta)
    check("banco gerado pelo código original", codigo_saida == 0, saida.splitlines()[-1] if saida else "")
    # Alterações com secure_delete OFF (simula um build do SQLite sem secure_delete):
    # - 60 contas excluídas: as senhas ficam em páginas da lista livre (freelist), que o UPDATE da
    #   etapa 1 não toca; só o VACUUM da etapa 2 as remove;
    # - troca da senha de A por uma mais longa: a célula é realocada e a antiga vira espaço livre na página.
    con = sqlite3.connect(db)
    con.execute("PRAGMA secure_delete = OFF")
    con.execute("DELETE FROM usuarios WHERE email LIKE 'x%@legado'")
    con.commit()
    if misto:
        from werkzeug.security import generate_password_hash
        MARCAS["hash-ok"] = "SENHA-" + secrets.token_hex(8)
        con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)", [
            ("Hash scrypt", "scrypt@x", generate_password_hash(MARCAS["hash-ok"]), "admin"),
            ("Hash pbkdf2", "pbkdf2@x", generate_password_hash(MARCAS["hash-ok"], method="pbkdf2:sha256:1000"), "cliente"),
            ("Sem credencial", "nulo@x", None, "cliente"),
            ("Formato invalido", "formato@x", "abc$def$ghi", "cliente"),
        ])
        con.commit()
    MARCAS["A-nova"] = a_nova = marca("A-nova") + "-" + secrets.token_hex(24)
    con.execute("UPDATE usuarios SET senha = ? WHERE email = 'a@legado'", (a_nova,))
    con.commit()
    log(f"páginas livres após as exclusões: {con.execute('PRAGMA freelist_count').fetchone()[0]}")
    con.close()
    return db


def legadas_esperadas(db):
    return [r[0] for r in q(db, "SELECT id, senha FROM usuarios ORDER BY id")
            if r[1] is not None and not str(r[1]).startswith(("scrypt:", "pbkdf2:"))]


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http(base, metodo, caminho, corpo=None, token=None):
    headers = {"Content-Type": "application/json"} if corpo is not None else {}
    if token:
        headers["X-Admin-Token"] = token
    data = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(base + caminho, data=data, method=metodo, headers=headers)
    try:
        with OPENER.open(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def cenario(nome, misto):
    log(f"## Cenário {nome}")
    pasta = tempfile.mkdtemp(prefix=f"f04_{nome}_", dir=WORK)
    db = gerar_legado(pasta, misto)
    legadas = legadas_esperadas(db)
    valores_legados = [v for k, v in MARCAS.items() if k in ("A-antiga", "A-nova", "B", "C-excluida")] + SEED_ORIGINAL
    if misto:
        valores_legados.append("abc$def$ghi")
    contagem = {t: len(v) for t, v in dump(db).items() if t != "sqlite_sequence"}
    log(f"contagens: {contagem}; credenciais legadas (ids): {legadas}; arquivos: {arquivos(pasta)}")
    ocorr = busca_bytes(pasta, valores_legados)
    check("antes: cada senha legada sintética e do seed original aparece nos bytes do arquivo (a busca é sensível)",
          all(ocorr[("loja.db", v)] >= 1 for v in valores_legados),
          ", ".join(f"{mascarar(v)}={ocorr[('loja.db', v)]}" for v in valores_legados))
    check("antes: a senha antiga de A está só como sobra (não está em nenhuma linha)",
          q(db, "SELECT COUNT(*) FROM usuarios WHERE senha = ?", (MARCAS["A-antiga"],))[0][0] == 0)
    dump_inicial, sha_inicial = dump(db), sha(db)

    # 1. Boot recusado, com seed ligado (padrão) e desligado, sem alterar o banco.
    for extra in ({}, {"SEED_ON_STARTUP": "0"}):
        codigo, saida = rodar(["app.py"], env_base(db, PORT=str(porta_livre()), **extra))
        rot = "seed padrão" if not extra else "SEED_ON_STARTUP=0"
        check(f"boot ({rot}): `python app.py` recusa com código 1 e indica migrar_senhas.py",
              codigo == 1 and "Inicialização recusada" in saida and "migrar_senhas.py" in saida
              and f"{len(legadas)} credencial(is) legada(s)" in saida and "SERVIDOR INICIADO" not in saida,
              saida.splitlines()[-1][:200])
        check(f"boot ({rot}): banco intacto (sha256 e dump idênticos, sem arquivos auxiliares)",
              sha(db) == sha_inicial and dump(db) == dump_inicial and arquivos(pasta) == ["loja.db"])
        check(f"boot ({rot}): nenhuma senha impressa", not any(v in saida for v in valores_legados if len(v) > 8))

    # 2. Simulação.
    mtime = os.stat(db).st_mtime_ns
    codigo, saida = rodar(["migrar_senhas.py", db])
    log("simulação: " + saida.replace("\n", " | "))
    check("simulação: código 0, contagem de legadas correta, nada gravado (sha256, mtime e arquivos iguais)",
          codigo == 0 and f"legadas={len(legadas)}" in saida and sha(db) == sha_inicial
          and os.stat(db).st_mtime_ns == mtime and arquivos(pasta) == ["loja.db"])

    # 3. Falha antes do commit (trigger na 2ª credencial legada), numa cópia.
    copia = tempfile.mkdtemp(prefix="rollback_", dir=WORK)
    db_r = os.path.join(copia, "loja.db")
    shutil.copy2(db, db_r)
    con = sqlite3.connect(db_r)
    con.execute(f"CREATE TRIGGER falha BEFORE UPDATE OF senha ON usuarios WHEN OLD.id = {legadas[1]} "
                "BEGIN SELECT RAISE(ABORT, 'falha induzida'); END")
    con.commit()
    con.close()
    sha_r, dump_r = sha(db_r), dump(db_r)
    codigo, saida = rodar(["migrar_senhas.py", db_r, "--aplicar"])
    check("falha antes do commit: código 1, transação desfeita, banco idêntico (sha256 e dump), sem auxiliares",
          codigo == 1 and "Transação desfeita" in saida and sha(db_r) == sha_r and dump(db_r) == dump_r
          and arquivos(copia) == ["loja.db"], saida.splitlines()[-1][:160])
    codigo, saida = rodar(["app.py"], env_base(db_r, PORT=str(porta_livre())))
    check("falha antes do commit: o boot continua recusado", codigo == 1 and "Inicialização recusada" in saida)

    # 4. Falha na limpeza (etapa 2, depois do commit) e retomada, numa cópia.
    copia = tempfile.mkdtemp(prefix="limpeza_", dir=WORK)
    db_l = os.path.join(copia, "loja.db")
    shutil.copy2(db, db_l)
    codigo, saida = rodar(["-c", "import sys, sqlite3, migrar_senhas\n"
                                 "def falhar(con): raise sqlite3.OperationalError('falha induzida na limpeza')\n"
                                 "migrar_senhas.limpar = falhar\n"
                                 f"sys.exit(migrar_senhas.main([{db_l!r}, '--aplicar']))"])
    sobra = total_ocorrencias(copia, [MARCAS["A-antiga"]])
    check("falha na limpeza: código 1, mensagem de retomada, credenciais já NULL",
          codigo == 1 and "execute novamente com --aplicar" in saida
          and q(db_l, "SELECT COUNT(*) FROM usuarios WHERE senha IS NOT NULL AND senha NOT LIKE 'scrypt:%' "
                      "AND senha NOT LIKE 'pbkdf2:%'")[0][0] == 0)
    sobra_c = total_ocorrencias(copia, [MARCAS["C-excluida"]])
    log(f"falha na limpeza (após a etapa 1, sem VACUUM): sobra da senha antiga de A = {sobra}; "
        f"senhas das contas excluídas na freelist = {sobra_c}")
    check("falha na limpeza: as senhas da freelist continuam no arquivo (a etapa 2 é necessária)", sobra_c > 0)
    sha_l = sha(db_l)
    codigo, saida = rodar(["app.py"], env_base(db_l, PORT=str(porta_livre())))
    check("falha na limpeza: boot recusado por limpeza pendente, sem alterar o banco",
          codigo == 1 and "limpeza física" in saida and sha(db_l) == sha_l, saida.splitlines()[-1][:160])
    codigo, saida = rodar(["migrar_senhas.py", db_l])
    check("falha na limpeza: a simulação informa limpeza_pendente=sim", codigo == 0 and "limpeza_pendente=sim" in saida)
    codigo, saida = rodar(["migrar_senhas.py", db_l, "--aplicar"])
    check("retomada: código 0 e 0 ocorrências de qualquer senha legada em todos os arquivos",
          codigo == 0 and total_ocorrencias(copia, valores_legados) == 0 and arquivos(copia) == ["loja.db"])

    # 5. Aplicação no banco do cenário.
    codigo, saida = rodar(["migrar_senhas.py", db, "--aplicar"])
    log("aplicar: " + saida.replace("\n", " | "))
    depois = dump(db)
    check("aplicar: código 0", codigo == 0)
    check("aplicar: 0 ocorrências de cada senha legada (inclusive a sobra e as do seed original) em todos os arquivos",
          total_ocorrencias(pasta, valores_legados) == 0 and arquivos(pasta)[:1] == ["loja.db"],
          f"arquivos={arquivos(pasta)}")
    check("aplicar: produtos, pedidos, itens_pedido e sqlite_sequence idênticos",
          all(depois[t] == dump_inicial[t] for t in ("produtos", "pedidos", "itens_pedido", "sqlite_sequence")))
    esperado = [r[:3] + ((None,) if r[0] in legadas else (r[3],)) + r[4:] for r in dump_inicial["usuarios"]]
    check(f"aplicar: usuarios com mesmos IDs, nomes, e-mails, perfis e datas; {len(legadas)} senha(s) NULL; hashes válidos idênticos",
          depois["usuarios"] == esperado)
    check("aplicar: PRAGMA integrity_check = ok", q(db, "PRAGMA integrity_check") == [("ok",)])
    check("aplicar: marca de limpeza removida (PRAGMA user_version = 0)", q(db, "PRAGMA user_version") == [(0,)])

    # 6. Boot aceito e logins.
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    log_srv = open(os.path.join(WORK, f"srv_{nome}.log"), "w")
    proc = subprocess.Popen([PY, "-B", "app.py"], cwd=REFAT, env=env_base(db, PORT=str(porta)),
                            stdout=log_srv, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                if http(base, "GET", "/health")[0] == 200:
                    break
            except OSError:
                time.sleep(0.25)
        st, corpo = http(base, "GET", "/health")
        check("boot após migração: aceito, /health 200 sem seed adicional",
              st == 200 and corpo["counts"] == {"produtos": 10, "usuarios": len(depois["usuarios"]), "pedidos": 2})
        recusados = [(e, MARCAS[k]) for e, k in (("a@legado", "A-nova"), ("a@legado", "A-antiga"), ("b@legado", "B"))]
        recusados += [("admin@loja.com", "admin123"), ("joao@email.com", "123456"), ("maria@email.com", "senha123")]
        if misto:
            recusados.append(("formato@x", "abc$def$ghi"))
        res = [http(base, "POST", "/login", {"email": e, "senha": s})[0] for e, s in recusados]
        check(f"login com cada credencial legada → 401 ({len(res)} contas/senhas)", res == [401] * len(res), str(res))
        if misto:
            ok = [http(base, "POST", "/login", {"email": e, "senha": MARCAS["hash-ok"]}) for e in ("scrypt@x", "pbkdf2@x")]
            check("login das contas com hash válido → 200, com o perfil preservado",
                  [(s, c["dados"]["tipo"]) for s, c in ok] == [(200, "admin"), (200, "cliente")], str([s for s, _ in ok]))
        st, corpo = http(base, "GET", "/pedidos", token=TOKEN)
        check("dados de negócio preservados e legíveis (GET /pedidos com token → 2 pedidos)",
              st == 200 and [p["id"] for p in corpo["dados"]] == [1, 2])
    finally:
        proc.terminate()
        proc.wait(10)
        log_srv.close()
    with open(os.path.join(WORK, f"srv_{nome}.log")) as fh:
        texto = fh.read()
    check("log do servidor sem traceback e sem senha", "Traceback" not in texto
          and not any(v in texto for v in valores_legados if len(v) > 8))
    check("boot e uso não alteraram os dados (dump idêntico ao pós-migração)", dump(db) == depois)

    # 7. Segunda execução.
    codigo, saida = rodar(["migrar_senhas.py", db])
    check("segunda simulação: legadas=0", codigo == 0 and "legadas=0" in saida, saida.splitlines()[0][:160])
    codigo, saida = rodar(["migrar_senhas.py", db, "--aplicar"])
    check("segunda aplicação: código 0, 0 invalidadas, dados idênticos",
          codigo == 0 and "0 credencial(is) invalidada(s)" in saida and dump(db) == depois)
    log()


WORK = tempfile.mkdtemp(prefix="f04_")
try:
    log("# F-04 — bancos do código original, recusa do boot e migrar_senhas.py")
    log(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}; senhas legadas sintéticas mascaradas como <marca-…>")
    log()
    cenario("legado", False)
    cenario("misto", True)
    log(f"Resultado: {'APROVADO' if not falhas else 'REPROVADO'} — {len(falhas)} falha(s)")
finally:
    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if falhas else 0)
