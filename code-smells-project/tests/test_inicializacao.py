"""Testes do F-13 (rodada 4): schema sempre preparado, seed controlado por SEED_ON_STARTUP e sem
duplicação no reinício, e conexão injetável por instância (R-10).

Executar a partir da raiz do projeto: python -B -m unittest discover -s tests -v
Senhas e tokens são gerados a cada execução (secrets) e nunca impressos.
"""
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import flask  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

import database  # noqa: E402
from app import create_app  # noqa: E402
from config import ConfigError, load_config  # noqa: E402
from controllers import pedido_controller, produto_controller  # noqa: E402

TABELAS = ("produtos", "usuarios", "pedidos", "itens_pedido")
EMAILS_DEMO = ("admin@loja.com", "joao@email.com", "maria@email.com")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PRODUTO = {"nome": "Produto Teste", "descricao": "d", "preco": 10.0, "estoque": 5, "categoria": "geral"}


def ler(caminho, sql, params=()):
    con = sqlite3.connect(caminho)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def tabelas(caminho):
    return sorted(r[0] for r in ler(caminho, "SELECT name FROM sqlite_master WHERE type = 'table' "
                                             "AND name NOT LIKE 'sqlite_%'"))


def contagens(caminho):
    return {t: ler(caminho, f"SELECT COUNT(*) FROM {t}")[0][0] for t in TABELAS}


def dump(caminho):
    return {t: ler(caminho, f"SELECT * FROM {t} ORDER BY id") for t in TABELAS}


@contextmanager
def servir(app):
    """Serve a instância por HTTP real (servidor WSGI do Werkzeug com threads) numa porta livre."""
    servidor = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        thread.join(5)
        servidor.server_close()


def http(base, metodo, caminho, corpo=None, token=None):
    headers = {}
    data = None
    if corpo is not None:
        data, headers["Content-Type"] = json.dumps(corpo).encode(), "application/json"
    if token is not None:
        headers["X-Admin-Token"] = token
    req = urllib.request.Request(base + caminho, data=data, method=metodo, headers=headers)
    try:
        with OPENER.open(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or "null")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token = secrets.token_urlsafe(16)
        # Senhas sintéticas de demonstração SEMPRE configuradas: no modo desligado, é a flag que impede a carga.
        self.senhas = {email: secrets.token_urlsafe(12) for email in EMAILS_DEMO}

    def tearDown(self):
        self.tmp.cleanup()

    def caminho(self, nome="loja.db"):
        return os.path.join(self.tmp.name, nome)

    def criar(self, db, seed, token=None, **kwargs):
        return create_app({
            "DATABASE_PATH": db,
            "SEED_ON_STARTUP": seed,
            "ADMIN_TOKEN": token or self.token,
            "SEED_SENHAS": dict(self.senhas),
            "TESTING": True,
        }, **kwargs)


class ConfiguracaoSeedTest(Base):
    def test_variavel_ausente_1_e_0(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEED_ON_STARTUP", None)
            self.assertIs(load_config()["SEED_ON_STARTUP"], True)
        for valor, esperado in (("1", True), ("0", False)):
            with mock.patch.dict(os.environ, {"SEED_ON_STARTUP": valor}):
                self.assertIs(load_config()["SEED_ON_STARTUP"], esperado)

    def test_valor_invalido_impede_boot_antes_de_abrir_o_banco(self):
        for valor in ("true", "false", "", "2", " 1", "0 ", "on", "sim"):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {"SEED_ON_STARTUP": valor}):
                db = self.caminho(f"invalido_{len(valor)}_{valor.strip() or 'vazio'}.db")
                with self.assertRaises(ConfigError):
                    create_app({"DATABASE_PATH": db})
                self.assertFalse(os.path.exists(db), "o arquivo de banco não pode ser criado")

    def test_override_da_factory_aceita_somente_bool(self):
        for valor in ("0", "1", 0, 1, None, "False"):
            with self.subTest(valor=valor):
                db = self.caminho(f"override_{valor!r}.db")
                with self.assertRaises(ConfigError):
                    self.criar(db, valor)
                self.assertFalse(os.path.exists(db))

    def test_variavel_de_ambiente_pela_factory(self):
        for valor, produtos in ((None, 10), ("1", 10), ("0", 0)):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {}):
                os.environ.pop("SEED_ON_STARTUP", None)
                if valor is not None:
                    os.environ["SEED_ON_STARTUP"] = valor
                db = self.caminho(f"env_{valor}.db")
                create_app({"DATABASE_PATH": db, "SEED_SENHAS": dict(self.senhas)})
                self.assertEqual(contagens(db)["produtos"], produtos)


class SeedDesligadoTest(Base):
    def test_s1_banco_novo_tabelas_vazias_e_api_grava_e_le(self):
        db = self.caminho()
        client = self.criar(db, False).test_client()
        self.assertEqual(tabelas(db), sorted(TABELAS))
        self.assertEqual(contagens(db), dict.fromkeys(TABELAS, 0))
        self.assertEqual(client.get("/produtos").get_json(), {"dados": [], "sucesso": True})
        self.assertEqual(client.get("/health").get_json()["counts"], {"produtos": 0, "usuarios": 0, "pedidos": 0})
        # A flag impede a carga mesmo com as senhas de demonstração configuradas.
        self.assertEqual(client.post("/login", json={"email": "admin@loja.com",
                                                     "senha": self.senhas["admin@loja.com"]}).status_code, 401)
        resp = client.post("/produtos", json=PRODUTO)
        self.assertEqual((resp.status_code, resp.get_json()["dados"]), (201, {"id": 1}))
        self.assertEqual(client.get("/produtos/1").get_json()["dados"]["nome"], "Produto Teste")
        resp = client.post("/usuarios", json={"nome": "Ana", "email": "ana@loja.com", "senha": "senha-da-ana"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(client.post("/login", json={"email": "ana@loja.com", "senha": "senha-da-ana"}).status_code, 200)
        resp = client.post("/pedidos", json={"usuario_id": 1, "itens": [{"produto_id": 1, "quantidade": 2}]})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(client.get("/pedidos").get_json()["dados"]), 1)
        self.assertEqual(contagens(db), {"produtos": 1, "usuarios": 1, "pedidos": 1, "itens_pedido": 1})

    def test_s2_reset_e_reinicio_com_seed_desligado_mantem_vazio(self):
        db = self.caminho()
        client = self.criar(db, True).test_client()
        self.assertEqual(contagens(db)["produtos"], 10)
        resp = client.post("/admin/reset-db", headers={"X-Admin-Token": self.token})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(contagens(db), dict.fromkeys(TABELAS, 0))
        client = self.criar(db, False).test_client()  # reinício
        self.assertEqual(contagens(db), dict.fromkeys(TABELAS, 0))
        self.assertEqual(client.get("/produtos").get_json(), {"dados": [], "sucesso": True})

    def test_s3_banco_populado_nao_e_alterado_com_seed_desligado(self):
        db = self.caminho()
        client = self.criar(db, True).test_client()
        client.post("/pedidos", json={"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 1}]})
        antes = dump(db)
        self.criar(db, False)
        self.assertEqual(dump(db), antes)


class SeedLigadoTest(Base):
    def test_s4_banco_novo_carga_esperada(self):
        db = self.caminho()
        client = self.criar(db, True).test_client()
        self.assertEqual(contagens(db), {"produtos": 10, "usuarios": 3, "pedidos": 0, "itens_pedido": 0})
        self.assertEqual([r[0] for r in ler(db, "SELECT email FROM usuarios ORDER BY id")], list(EMAILS_DEMO))
        for (senha,) in ler(db, "SELECT senha FROM usuarios"):
            self.assertTrue(senha.startswith(("scrypt:", "pbkdf2:")))
        for email, senha in self.senhas.items():
            self.assertEqual(client.post("/login", json={"email": email, "senha": senha}).status_code, 200)

    def test_s5_reinicio_nao_duplica(self):
        db = self.caminho()
        self.criar(db, True)
        antes = dump(db)
        self.criar(db, True)
        self.criar(db, True)
        self.assertEqual(dump(db), antes)

    def test_s6_reset_e_reinicio_repoe_a_demonstracao(self):
        db = self.caminho()
        client = self.criar(db, True).test_client()
        client.post("/admin/reset-db", headers={"X-Admin-Token": self.token})
        self.assertEqual(contagens(db), dict.fromkeys(TABELAS, 0))
        self.criar(db, True)
        self.assertEqual(contagens(db), {"produtos": 10, "usuarios": 3, "pedidos": 0, "itens_pedido": 0})

    def test_s7_produtos_vazios_com_usuarios_existentes_nao_duplica_nem_altera_usuarios(self):
        db = self.caminho()
        client = self.criar(db, True).test_client()
        for produto_id in range(1, 11):
            self.assertEqual(client.delete(f"/produtos/{produto_id}").status_code, 200)
        con = sqlite3.connect(db)
        con.execute("UPDATE usuarios SET tipo = 'cliente', nome = 'Admin Alterado' WHERE email = 'admin@loja.com'")
        con.commit()
        con.close()
        usuarios_antes = ler(db, "SELECT * FROM usuarios ORDER BY id")
        self.senhas = {email: secrets.token_urlsafe(12) for email in EMAILS_DEMO}  # novas senhas no reinício
        self.criar(db, True)
        self.assertEqual(contagens(db)["produtos"], 10)
        self.assertEqual(ler(db, "SELECT * FROM usuarios ORDER BY id"), usuarios_antes,
                         "usuários existentes: mesma quantidade, senha e perfil")


class SubstituicaoConexaoTest(Base):
    """R-10: a dependência de conexão é da instância e pode ser substituída no fluxo real."""

    def test_fabrica_injetada_e_usada_pelo_fluxo_http_real(self):
        banco_injetado = self.caminho("injetado.db")
        banco_configurado = self.caminho("nao_usar.db")
        registro = {"abertas": 0, "fechadas": 0}

        class ConexaoEspia(sqlite3.Connection):
            def close(self):
                registro["fechadas"] += 1
                super().close()

        def fabrica():
            registro["abertas"] += 1
            con = sqlite3.connect(banco_injetado, factory=ConexaoEspia, check_same_thread=False)
            con.row_factory = sqlite3.Row
            return con

        app = create_app({"DATABASE_PATH": banco_configurado, "SEED_ON_STARTUP": True, "ADMIN_TOKEN": self.token,
                          "SEED_SENHAS": dict(self.senhas)}, connection_factory=fabrica)
        self.assertGreaterEqual(registro["abertas"], 1, "schema e seed do boot passam pela fábrica")
        self.assertEqual(contagens(banco_injetado)["produtos"], 10)
        abertas_boot = registro["abertas"]

        with servir(app) as base:
            status, corpo = http(base, "GET", "/produtos")
            self.assertEqual((status, len(corpo["dados"])), (200, 10))
            status, corpo = http(base, "POST", "/pedidos",
                                 {"usuario_id": 2, "itens": [{"produto_id": 2, "quantidade": 3}]})
            self.assertEqual(status, 201)
            pedido_id = corpo["dados"]["pedido_id"]
            status, _ = http(base, "PUT", f"/pedidos/{pedido_id}/status", {"status": "aprovado"})
            self.assertEqual(status, 200)
            status, corpo = http(base, "GET", "/health")
            self.assertEqual((status, corpo["counts"]["pedidos"]), (200, 1))
            status, corpo = http(base, "GET", "/usuarios", token=self.token)
            self.assertEqual((status, len(corpo["dados"])), (200, 3))

        self.assertEqual(registro["abertas"] - abertas_boot, 5, "uma conexão injetada por requisição")
        prazo = time.time() + 5
        while registro["fechadas"] < registro["abertas"] and time.time() < prazo:
            time.sleep(0.05)
        self.assertEqual(registro["fechadas"], registro["abertas"], "toda conexão injetada é fechada no teardown")
        self.assertFalse(os.path.exists(banco_configurado), "DATABASE_PATH não foi aberto")
        self.assertEqual(ler(banco_injetado, "SELECT status FROM pedidos WHERE id = ?", (pedido_id,)), [("aprovado",)])
        self.assertEqual(ler(banco_injetado, "SELECT estoque FROM produtos WHERE id = 2"), [(47,)])

    def test_caso_de_uso_sem_contexto_flask(self):
        db = self.caminho()
        self.criar(db, True)
        self.assertFalse(flask.has_app_context())
        con = database.connect(db)
        try:
            produtos = produto_controller.listar_produtos(con)
            resultado = pedido_controller.criar_pedido(con, {"usuario_id": 2, "itens": [{"produto_id": 1, "quantidade": 1}]})
            pedido_controller.atualizar_status_pedido(con, resultado["pedido_id"], {"status": "enviado"})
            pedidos = pedido_controller.listar_todos_pedidos(con)
        finally:
            con.close()
        self.assertFalse(flask.has_app_context())
        self.assertEqual(len(produtos), 10)
        self.assertEqual([(p["id"], p["status"]) for p in pedidos], [(resultado["pedido_id"], "enviado")])
        self.assertEqual(ler(db, "SELECT estoque FROM produtos WHERE id = 1"), [(9,)])

    def test_controllers_nao_dependem_de_flask_nem_de_get_db(self):
        pasta = os.path.join(PROJECT_ROOT, "controllers")
        for nome in sorted(os.listdir(pasta)):
            if nome.endswith(".py"):
                with self.subTest(arquivo=nome), open(os.path.join(pasta, nome), encoding="utf-8") as fh:
                    codigo = fh.read()
                    self.assertNotIn("flask", codigo)
                    self.assertNotIn("get_db", codigo)
                    self.assertNotIn("import database", codigo)


class DuasInstanciasTest(Base):
    def test_duas_instancias_no_mesmo_processo_com_bancos_isolados(self):
        db_a, db_b = self.caminho("a.db"), self.caminho("b.db")
        token_a, token_b = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        # Este cenário exercita a geração de chaves efêmeras, inclusive em shells configurados.
        with mock.patch.dict(os.environ):
            os.environ.pop("SECRET_KEY", None)
            app_a = self.criar(db_a, True, token=token_a)
            app_b = self.criar(db_b, False, token=token_b)
        self.assertNotEqual(app_a.config["SECRET_KEY"], app_b.config["SECRET_KEY"])
        self.assertEqual(contagens(db_a)["produtos"], 10)
        self.assertEqual(contagens(db_b)["produtos"], 0)

        with servir(app_a) as base_a, servir(app_b) as base_b:
            # Intercaladas.
            self.assertEqual(http(base_a, "POST", "/produtos", dict(PRODUTO, nome="Somente A"))[0], 201)
            self.assertEqual(http(base_b, "GET", "/produtos")[1], {"dados": [], "sucesso": True})
            self.assertEqual(http(base_b, "POST", "/produtos", dict(PRODUTO, nome="Somente B"))[0], 201)
            self.assertEqual(len(http(base_a, "GET", "/produtos")[1]["dados"]), 11)
            self.assertEqual(http(base_b, "GET", "/usuarios", token=token_a)[0], 401)
            self.assertEqual(http(base_b, "GET", "/usuarios", token=token_b), (200, {"dados": [], "sucesso": True}))
            self.assertEqual(http(base_a, "GET", "/usuarios", token=token_b)[0], 401)

            # Simultâneas: as threads começam juntas e gravam nas duas instâncias ao mesmo tempo.
            barreira = threading.Barrier(16)
            erros = []

            def gravar(base, nome):
                barreira.wait()
                status, _ = http(base, "POST", "/produtos", dict(PRODUTO, nome=nome))
                if status != 201:
                    erros.append((nome, status))

            threads = [threading.Thread(target=gravar, args=(base_a if i % 2 == 0 else base_b,
                                                             f"{'A' if i % 2 == 0 else 'B'}-{i:02d}"))
                       for i in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        self.assertEqual(erros, [])
        nomes_a = {r[0] for r in ler(db_a, "SELECT nome FROM produtos WHERE id > 10")}
        nomes_b = {r[0] for r in ler(db_b, "SELECT nome FROM produtos")}
        self.assertEqual(nomes_a, {"Somente A"} | {f"A-{i:02d}" for i in range(0, 16, 2)})
        self.assertEqual(nomes_b, {"Somente B"} | {f"B-{i:02d}" for i in range(1, 16, 2)})
        self.assertEqual(contagens(db_a)["produtos"], 19)
        self.assertEqual(contagens(db_b), {"produtos": 9, "usuarios": 0, "pedidos": 0, "itens_pedido": 0})


if __name__ == "__main__":
    unittest.main()
