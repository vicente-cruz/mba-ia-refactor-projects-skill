"""F-09: pedidos concorrentes por HTTP real sobre o mesmo arquivo SQLite (rodada 5).

Uso: python -B f09_concorrencia.py <dir_projeto> <saida.txt>

- Cada rodada cria um banco temporário novo (seed desligado), um usuário e um produto com estoque K.
- A aplicação é servida por werkzeug.serving.make_server(threaded=True): uma thread e uma conexão
  sqlite3 distinta por requisição (fábrica padrão de create_app, ou a fábrica "lenta" abaixo,
  que abre o MESMO arquivo e só acrescenta atraso depois de ler o estoque, para alargar a janela
  entre checagem e baixa).
- N clientes HTTP disparam ao mesmo tempo (barreira) um pedido válido de 1 unidade.
- Critério: exatamente K respostas 201; as demais 400 com o corpo de estoque insuficiente;
  estoque final 0; pedidos e itens só dos sucessos; nenhum 500; nenhum traceback no servidor.
- A sobreposição é medida no servidor: requisições simultâneas em andamento (middleware WSGI) e
  quantas leituras de estoque viram unidade disponível (> K prova que a corrida aconteceu).
- Rollback por falha induzida (trigger): sequencial e concorrente.
"""
import http.client
import json
import logging
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import time

PROJETO, SAIDA = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, PROJETO)
os.chdir(PROJETO)

from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402

NOME = "Produto Concorrente"
PRECO = 10.0
CORPO_RECUSA = {"erro": "Estoque insuficiente para " + NOME, "sucesso": False}
ATRASO = 0.05

linhas, falhas = [], []


class CapturaLog(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.registros = []

    def emit(self, record):
        self.registros.append(self.format(record))


captura = CapturaLog()
logging.getLogger().addHandler(captura)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


def log(texto=""):
    linhas.append(texto)
    print(texto, flush=True)


def check(nome, condicao, detalhe=""):
    log(("OK   " if condicao else "FALHA") + " " + nome + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


class Medidor:
    """Middleware WSGI: conta requisições em andamento ao mesmo tempo no servidor."""

    def __init__(self, wsgi):
        self.wsgi, self.trava, self.ativos, self.maximo = wsgi, threading.Lock(), 0, 0

    def __call__(self, environ, start_response):
        with self.trava:
            self.ativos += 1
            self.maximo = max(self.maximo, self.ativos)
        try:
            return list(self.wsgi(environ, start_response))
        finally:
            with self.trava:
                self.ativos -= 1


class Leituras:
    def __init__(self):
        self.trava, self.disponivel, self.total = threading.Lock(), 0, 0


def fabrica_lenta(caminho, leituras):
    class _Cursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    class ConexaoLenta(sqlite3.Connection):
        def execute(self, sql, params=()):
            if "FROM produtos WHERE id" in sql and "estoque" in sql and sql.lstrip().upper().startswith("SELECT"):
                rows = super().execute(sql, params).fetchall()  # consome o cursor: libera o lock de leitura
                with leituras.trava:
                    leituras.total += 1
                    if rows and rows[0]["estoque"] >= 1:
                        leituras.disponivel += 1
                time.sleep(ATRASO)
                return _Cursor(rows)
            return super().execute(sql, params)

    def abrir():
        con = sqlite3.connect(caminho, factory=ConexaoLenta)
        con.row_factory = sqlite3.Row
        return con

    return abrir


def preparar(caminho, estoque, gatilho=None):
    con = sqlite3.connect(caminho)
    con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Cliente', 'cliente@teste', NULL, 'cliente')")
    con.execute("INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, 'x', ?, ?, 'geral')",
                (NOME, PRECO, estoque))
    if gatilho:
        con.execute(gatilho)
    con.commit()
    con.close()


def estado(caminho):
    con = sqlite3.connect(caminho)
    try:
        return {
            "estoque": con.execute("SELECT estoque FROM produtos WHERE id = 1").fetchone()[0],
            "pedidos": con.execute("SELECT id, usuario_id, status, total FROM pedidos ORDER BY id").fetchall(),
            "itens": con.execute("SELECT pedido_id, produto_id, quantidade, preco_unitario FROM itens_pedido ORDER BY id").fetchall(),
        }
    finally:
        con.close()


def disparar(porta, corpos):
    barreira = threading.Barrier(len(corpos))
    respostas = [None] * len(corpos)

    def cliente(i):
        conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
        dados = json.dumps(corpos[i])
        barreira.wait()
        try:
            conexao.request("POST", "/pedidos", body=dados, headers={"Content-Type": "application/json"})
            r = conexao.getresponse()
            respostas[i] = (r.status, json.loads(r.read().decode()))
        except Exception as erro:  # registrado como falha do caso
            respostas[i] = ("excecao", repr(erro))
        finally:
            conexao.close()

    threads = [threading.Thread(target=cliente, args=(i,)) for i in range(len(corpos))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return respostas


def rodada(n, k, lenta, gatilho=None, corpos=None):
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "loja.db")
        leituras = Leituras()
        fabrica = fabrica_lenta(caminho, leituras) if lenta else None
        app = create_app({"DATABASE_PATH": caminho, "SEED_ON_STARTUP": False,
                          "ADMIN_TOKEN": secrets.token_urlsafe(16)}, connection_factory=fabrica)
        preparar(caminho, k, gatilho)
        medidor = Medidor(app.wsgi_app)
        app.wsgi_app = medidor
        servidor = make_server("127.0.0.1", 0, app, threaded=True)
        porta = servidor.server_port
        t = threading.Thread(target=servidor.serve_forever, daemon=True)
        t.start()
        captura.registros.clear()
        try:
            corpos = corpos or [{"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 1}]}] * n
            respostas = disparar(porta, corpos)
        finally:
            servidor.shutdown()
            t.join()
        return respostas, estado(caminho), medidor.maximo, leituras, list(captura.registros)


def avaliar(rotulo, n, k, lenta, repeticoes):
    resumo = {"max_simultaneas": 0, "leituras_disponiveis": [], "ok": 0}
    for r in range(repeticoes):
        respostas, est, maximo, leituras, logs = rodada(n, k, lenta)
        sucessos = [b for s, b in respostas if s == 201]
        recusas = [b for s, b in respostas if s == 400]
        outros = [(s, b) for s, b in respostas if s not in (201, 400)]
        ids = sorted(b["dados"]["pedido_id"] for b in sucessos)
        criterios = {
            "K sucessos": len(sucessos) == k,
            "demais recusados por estoque": len(recusas) == n - k and all(b == CORPO_RECUSA for b in recusas),
            "sem 500 / exceção": not outros,
            "estoque final 0": est["estoque"] == 0,
            "pedidos = sucessos": [p[0] for p in est["pedidos"]] == ids and all(p[3] == PRECO for p in est["pedidos"]),
            "itens = sucessos": sorted(i[0] for i in est["itens"]) == ids and all(i[1:] == (1, 1, PRECO) for i in est["itens"]),
            "sem traceback/locked no servidor": not any("Traceback" in l or "locked" in l or "Erro não tratado" in l for l in logs),
        }
        resumo["max_simultaneas"] = max(resumo["max_simultaneas"], maximo)
        if lenta:
            resumo["leituras_disponiveis"].append(leituras.disponivel)
        if all(criterios.values()):
            resumo["ok"] += 1
        else:
            check(f"{rotulo} repetição {r + 1}", False,
                  json.dumps({c: v for c, v in criterios.items() if not v}, ensure_ascii=False)
                  + f" status={sorted(str(s) for s, _ in respostas)} estoque={est['estoque']} outros={outros[:3]} logs={logs[:2]}")
    check(f"{rotulo}: {resumo['ok']}/{repeticoes} repetições com exatamente {k} sucessos, {n - k} recusas 400, "
          f"estoque 0, pedidos/itens só dos sucessos, sem 500", resumo["ok"] == repeticoes)
    check(f"{rotulo}: sobreposição no servidor (máximo de requisições simultâneas = {resumo['max_simultaneas']})",
          resumo["max_simultaneas"] >= 2)
    if lenta:
        minimo = min(resumo["leituras_disponiveis"])
        check(f"{rotulo}: corrida exercitada (leituras de estoque com unidade disponível por repetição: "
              f"mín {minimo}, máx {max(resumo['leituras_disponiveis'])}; K = {k})", minimo > k)


def rollback():
    gatilho = ("CREATE TRIGGER falha_induzida BEFORE INSERT ON itens_pedido WHEN NEW.quantidade = 2 "
               "BEGIN SELECT RAISE(ABORT, 'falha induzida'); END")
    # Sequencial: pedido com 2 unidades falha ao gravar o item.
    respostas, est, _, _, logs = rodada(1, 5, False, gatilho,
                                        [{"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 2}]}])
    check("rollback sequencial: falha induzida → 500 genérico (esperado pela falha injetada)",
          respostas == [(500, {"erro": "Erro interno do servidor"})], str(respostas))
    check("rollback sequencial: 0 pedidos, 0 itens, estoque 5 intacto",
          est["pedidos"] == [] and est["itens"] == [] and est["estoque"] == 5, str(est))
    # Concorrente: 10 pedidos de 1 unidade (válidos) + 10 de 2 unidades (falha induzida), estoque 30.
    corpos = ([{"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 1}]}] * 10
              + [{"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 2}]}] * 10)
    for lenta in (False, True):
        respostas, est, maximo, _, _ = rodada(20, 30, lenta, gatilho, corpos)
        ok = sum(1 for s, _ in respostas[:10] if s == 201)
        induz = sum(1 for s, b in respostas[10:] if s == 500 and b == {"erro": "Erro interno do servidor"})
        ids = sorted(b["dados"]["pedido_id"] for s, b in respostas if s == 201)
        rot = "lenta" if lenta else "natural"
        check(f"rollback concorrente ({rot}, simultâneas={maximo}): 10 válidos → 201 e 10 com falha induzida → 500",
              ok == 10 and induz == 10, str(sorted(str(s) for s, _ in respostas)))
        check(f"rollback concorrente ({rot}): estoque 20, pedidos e itens só dos 10 válidos",
              est["estoque"] == 20 and [p[0] for p in est["pedidos"]] == ids and len(est["itens"]) == 10
              and all(i[2] == 1 for i in est["itens"]), f"estoque={est['estoque']} pedidos={len(est['pedidos'])} itens={len(est['itens'])}")


log(f"# F-09 — concorrência e rollback — projeto: {os.path.basename(os.path.dirname(PROJETO.rstrip('/')))}/{os.path.basename(PROJETO.rstrip('/'))}")
log(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}; atraso da fábrica lenta: {ATRASO}s")
log()
log("## Concorrência: N pedidos de 1 unidade, estoque K")
avaliar("N=20, K=5, conexão padrão", 20, 5, False, 20)
avaliar("N=20, K=5, fábrica lenta (mesmo arquivo)", 20, 5, True, 20)
avaliar("N=2, K=1, conexão padrão", 2, 1, False, 50)
avaliar("N=2, K=1, fábrica lenta (mesmo arquivo)", 2, 1, True, 50)
avaliar("N=50, K=10, fábrica lenta (mesmo arquivo)", 50, 10, True, 5)
log()
log("## Rollback por falha induzida (trigger em itens_pedido)")
rollback()
log()
log(f"Resultado: {'APROVADO' if not falhas else 'REPROVADO'} — {len(falhas)} falha(s)")
with open(SAIDA, "w", encoding="utf-8") as fh:
    fh.write("\n".join(linhas) + "\n")
sys.exit(1 if falhas else 0)
