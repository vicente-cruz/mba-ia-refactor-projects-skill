"""Rodada 5: controle de acesso (F-11/F-22), /health sem ambiente (F-07) e credenciais legadas (F-04).

Executar a partir da raiz do projeto:
    python -B -m unittest discover -s tests -v
Tokens e senhas são sintéticos, gerados a cada execução e nunca impressos.
"""
import contextlib
import hashlib
import io
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import database  # noqa: E402
import migrar_senhas  # noqa: E402
from app import create_app  # noqa: E402
from models import usuario  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

DESABILITADA = {"erro": "Operação administrativa desabilitada"}
NAO_AUTORIZADO = {"erro": "Não autorizado"}
PRODUTO = {"nome": "Produto Teste", "descricao": "d", "preco": 10.0, "estoque": 5, "categoria": "geral"}
TABELAS = ("produtos", "usuarios", "pedidos", "itens_pedido")


def dump(caminho):
    con = sqlite3.connect(caminho)
    try:
        return {t: con.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in TABELAS}
    finally:
        con.close()


def sha256(caminho):
    with open(caminho, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class AcessoAdministrativoTest(unittest.TestCase):
    """D-10 (a) e D-11 (a): mesma proteção de /admin/*: 403 sem configuração, 401 sem token ou errado."""

    ROTAS = [
        ("GET", "/pedidos", None, 200),
        ("GET", "/pedidos/usuario/2", None, 200),
        ("PUT", "/pedidos/1/status", {"status": "aprovado"}, 200),
        ("POST", "/produtos", PRODUTO, 201),
        ("PUT", "/produtos/1", dict(PRODUTO, nome="Alterado", preco=0), 200),
        ("DELETE", "/produtos/2", None, 200),
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "loja.db")
        self.token = secrets.token_urlsafe(16)
        self.app = create_app({"DATABASE_PATH": self.db, "ADMIN_TOKEN": self.token, "TESTING": True,
                               "SEED_SENHAS": {"joao@email.com": secrets.token_urlsafe(12)}})
        self.client = self.app.test_client()
        resp = self.client.post("/pedidos", json={"usuario_id": 2, "itens": [{"produto_id": 3, "quantidade": 1}]})
        self.assertEqual(resp.status_code, 201)  # criação de pedido continua pública

    def tearDown(self):
        self.tmp.cleanup()

    def chamar(self, metodo, caminho, corpo, headers=None):
        return self.client.open(caminho, method=metodo, json=corpo, headers=headers or {})

    def test_recusas_nao_alteram_dados(self):
        for metodo, caminho, corpo, _ in self.ROTAS:
            for rotulo, headers, status, esperado in [
                ("ausente", {}, 401, NAO_AUTORIZADO),
                ("incorreto", {"X-Admin-Token": self.token + "x"}, 401, NAO_AUTORIZADO),
                ("vazio", {"X-Admin-Token": ""}, 401, NAO_AUTORIZADO),
            ]:
                with self.subTest(rota=f"{metodo} {caminho}", token=rotulo):
                    antes = dump(self.db)
                    resp = self.chamar(metodo, caminho, corpo, headers)
                    self.assertEqual((resp.status_code, resp.get_json()), (status, esperado))
                    self.assertEqual(dump(self.db), antes)

    def test_operacao_desabilitada_sem_admin_token_configurado(self):
        self.app.config["ADMIN_TOKEN"] = None
        for metodo, caminho, corpo, _ in self.ROTAS:
            for headers in ({}, {"X-Admin-Token": self.token}):
                with self.subTest(rota=f"{metodo} {caminho}", com_token=bool(headers)):
                    antes = dump(self.db)
                    resp = self.chamar(metodo, caminho, corpo, headers)
                    self.assertEqual((resp.status_code, resp.get_json()), (403, DESABILITADA))
                    self.assertEqual(dump(self.db), antes)

    def test_token_valido_executa_a_operacao(self):
        auth = {"X-Admin-Token": self.token}
        resp = self.chamar("GET", "/pedidos", None, auth)
        self.assertEqual((resp.status_code, len(resp.get_json()["dados"])), (200, 1))
        resp = self.chamar("GET", "/pedidos/usuario/2", None, auth)
        self.assertEqual([p["id"] for p in resp.get_json()["dados"]], [1])
        self.assertEqual(self.chamar("PUT", "/pedidos/1/status", {"status": "aprovado"}, auth).status_code, 200)
        self.assertEqual(dump(self.db)["pedidos"][0][2], "aprovado")
        resp = self.chamar("POST", "/produtos", PRODUTO, auth)
        self.assertEqual((resp.status_code, resp.get_json()["dados"]), (201, {"id": 11}))
        self.assertEqual(self.chamar("PUT", "/produtos/1", dict(PRODUTO, nome="Alterado"), auth).status_code, 200)
        self.assertEqual(dump(self.db)["produtos"][0][1], "Alterado")
        self.assertEqual(self.chamar("DELETE", "/produtos/2", None, auth).status_code, 200)
        self.assertNotIn(2, [p[0] for p in dump(self.db)["produtos"]])

    def test_autorizacao_vem_antes_da_validacao(self):
        for metodo, caminho in [("POST", "/produtos"), ("PUT", "/produtos/1"), ("PUT", "/pedidos/1/status")]:
            with self.subTest(rota=f"{metodo} {caminho}"):
                resp = self.client.open(caminho, method=metodo, data="x", content_type="text/plain")
                self.assertEqual((resp.status_code, resp.get_json()), (401, NAO_AUTORIZADO))

    def test_rotas_do_cliente_continuam_publicas(self):
        self.assertEqual(self.client.get("/produtos").status_code, 200)
        self.assertEqual(self.client.get("/produtos/1").status_code, 200)
        self.assertEqual(self.client.get("/produtos/busca?q=Mouse").status_code, 200)
        self.assertEqual(self.client.post("/usuarios", json={"nome": "Ana", "email": "ana@x", "senha": "s1"}).status_code, 201)
        self.assertEqual(self.client.post("/login", json={"email": "ana@x", "senha": "s1"}).status_code, 200)


class HealthTest(unittest.TestCase):
    """D-9 (b): /health sem o campo ambiente; demais campos e caminho de erro preservados."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "loja.db")
        self.segredos = {"SECRET_KEY": secrets.token_hex(32), "ADMIN_TOKEN": secrets.token_urlsafe(16),
                         "senha": secrets.token_urlsafe(12)}

    def tearDown(self):
        self.tmp.cleanup()

    def criar(self, **kwargs):
        return create_app({"DATABASE_PATH": self.db, "SECRET_KEY": self.segredos["SECRET_KEY"],
                           "ADMIN_TOKEN": self.segredos["ADMIN_TOKEN"], "TESTING": True,
                           "SEED_SENHAS": {"admin@loja.com": self.segredos["senha"]}}, **kwargs)

    def assert_sem_segredos(self, texto):
        for nome, valor in self.segredos.items():
            self.assertNotIn(valor, texto, nome)
        for proibido in (self.db, self.tmp.name, "scrypt:", "pbkdf2:", "secret_key", "db_path", "ambiente"):
            self.assertNotIn(proibido, texto)

    def test_caminho_ok(self):
        resp = self.criar().test_client().get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "ok", "database": "connected",
                                           "counts": {"produtos": 10, "usuarios": 1, "pedidos": 0},
                                           "versao": "1.0.0", "debug": False})
        self.assert_sem_segredos(resp.get_data(as_text=True))

    def test_caminho_de_erro(self):
        app = self.criar()
        con = sqlite3.connect(self.db)
        con.execute("ALTER TABLE pedidos RENAME TO pedidos_x")
        con.commit()
        con.close()
        with self.assertLogs("controllers.sistema_controller", "ERROR"):
            resp = app.test_client().get("/health")
        self.assertEqual((resp.status_code, resp.get_json()),
                         (500, {"status": "erro", "detalhes": "Banco de dados indisponível"}))
        self.assert_sem_segredos(resp.get_data(as_text=True))

    def test_caminho_de_erro_ao_abrir_conexao(self):
        estado = {"falhar": False}

        def fabrica():
            if estado["falhar"]:
                raise sqlite3.OperationalError("unable to open database file")
            return database.connect(self.db)

        app = self.criar(connection_factory=fabrica)
        estado["falhar"] = True
        with self.assertLogs("controllers.sistema_controller", "ERROR"):
            resp = app.test_client().get("/health")
        self.assertEqual((resp.status_code, resp.get_json()),
                         (500, {"status": "erro", "detalhes": "Banco de dados indisponível"}))


GIGANTE = "scrypt:" + "9" * 4400 + ":8:1$s$" + "a" * 128
HASHES = {m: generate_password_hash("x", method=m) for m in ("scrypt", "pbkdf2", "pbkdf2:sha256:1000", "pbkdf2:sha512:600000")}
# Revisão 2: hashes válidos do Werkzeug que uma versão anterior da classificação invalidava.
HASHES.update({
    "pbkdf2:sha512_256:600000": generate_password_hash("x", method="pbkdf2:sha512_256:600000"),
    "pbkdf2:sha512_224:600000": generate_password_hash("x", method="pbkdf2:sha512_224:600000"),
    "scrypt salt_length=129": generate_password_hash("x", method="scrypt", salt_length=129),
    "pbkdf2:sha256:1000 salt_length=500": generate_password_hash("x", method="pbkdf2:sha256:1000", salt_length=500),
})


def criar_banco(caminho, usuarios):
    """Banco com o schema da aplicação, um pedido e os usuários informados (senha armazenada como está)."""
    con = sqlite3.connect(caminho)
    for comando in database.SCHEMA:
        con.execute(comando)
    con.executemany("INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)",
                    database.PRODUTOS_SEED)
    con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)", usuarios)
    con.execute("INSERT INTO pedidos (usuario_id, status, total) VALUES (1, 'aprovado', 89.9)")
    con.execute("INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (1, 2, 1, 89.9)")
    con.commit()
    con.close()


class CredenciaisLegadasTest(unittest.TestCase):
    """D-4R (d) + (ii): boot recusado com credencial legada; migrar_senhas.py invalida todas."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "loja.db")
        self.marca = "LEGADO-" + secrets.token_hex(8)  # texto puro sintético e rastreável
        self.senha_hash = secrets.token_urlsafe(12)
        self.usuarios = [
            ("Legado", "legado@x", self.marca, "admin"),
            ("Hash", "hash@x", generate_password_hash(self.senha_hash), "cliente"),
            ("Formato", "formato@x", "abc$def$ghi", "cliente"),
            ("Sem senha", "nulo@x", None, "cliente"),
            ("Pbkdf2", "pbkdf2@x", generate_password_hash(self.senha_hash, method="pbkdf2:sha256:1000"), "cliente"),
            ("Estrutura", "estrutura@x", "scrypt:9999999999:9999999999:9999999999$salt$00", "cliente"),
        ]
        criar_banco(self.db, self.usuarios)

    def tearDown(self):
        self.tmp.cleanup()

    def arquivos(self):
        return sorted(os.listdir(self.tmp.name))

    def migrar(self, *args):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = migrar_senhas.main([self.db, *args])
        return codigo, saida.getvalue() + erro.getvalue()

    def bytes_contem(self, valor):
        alvo, resultado = valor.encode(), {}
        for nome in self.arquivos():
            with open(os.path.join(self.tmp.name, nome), "rb") as fh:
                resultado[nome] = alvo in fh.read()
        return resultado

    def test_classificacao(self):
        for metodo in ("scrypt", "pbkdf2", "pbkdf2:sha256:1000", "pbkdf2:sha512:600000"):
            with self.subTest(metodo=metodo):
                self.assertTrue(usuario.hash_preservavel(generate_password_hash("x", method=metodo)))
        for valor in (self.marca, "", "abc$def$ghi", "scrypt:9999999999:9999999999:9999999999$salt$00",
                      "pbkdf2:sha256:1000$salt$00", "scrypt:32768:8:1$salt$" + "0" * 127, None, 123):
            with self.subTest(valor=str(valor)[:20]):
                self.assertFalse(usuario.hash_preservavel(valor))
        con = database.connect(self.db)
        try:
            self.assertEqual(usuario.ids_com_credencial_legada(con), [1, 3, 6])
        finally:
            con.close()

    def test_classificacao_de_texto_legado_arbitrario_sem_excecao_nem_kdf(self):
        arbitrarios = [GIGANTE, "pbkdf2:sha256:" + "9" * 5000 + "$salt$" + "a" * 64,
                       "scrypt:" + "1" * 11 + ":8:1$s$" + "a" * 128, "scrypt:" + "4" * 20 + ":8:1$s$" + "a" * 128,
                       "scrypt:" + str(2 ** 64) + ":8:1$s$" + "a" * 128, "pbkdf2:sha256:1000$" + "s" * 500 + "$" + "a" * 63,
                       "pbkdf2:nao_existe:1000$salt$" + "a" * 64, "scrypt:32768:8:1$salt$" + "A" * 128,
                       b"texto-em-blob", 3.5]
        # Nenhum cálculo de hash: KDFs e verificação do Werkzeug falhariam se fossem chamados.
        with mock.patch("hashlib.scrypt", side_effect=AssertionError("scrypt chamado")), \
                mock.patch("hashlib.pbkdf2_hmac", side_effect=AssertionError("pbkdf2 chamado")), \
                mock.patch.object(usuario, "check_password_hash", side_effect=AssertionError("check chamado")):
            for valor in arbitrarios:
                with self.subTest(valor=repr(valor)[:30]):
                    self.assertFalse(usuario.hash_preservavel(valor))
            for metodo, valor in HASHES.items():
                with self.subTest(metodo=metodo):
                    self.assertTrue(usuario.hash_preservavel(valor))

    def test_texto_legado_gigante_boot_simulacao_e_aplicacao(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE usuarios SET senha = ? WHERE id = 1", (GIGANTE,))
        con.commit()
        con.close()
        antes = sha256(self.db)
        with self.assertRaises(database.MigracaoPendenteError) as ctx:
            create_app({"DATABASE_PATH": self.db, "TESTING": True})
        self.assertIn("3 credencial(is) legada(s)", str(ctx.exception))
        self.assertEqual(sha256(self.db), antes)
        codigo, saida = self.migrar()
        self.assertEqual((codigo, "legadas=3" in saida), (0, True), saida)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(dump(self.db)["usuarios"][0][3], None)
        self.assertEqual(self.bytes_contem("9" * 1000), {"loja.db": False})
        create_app({"DATABASE_PATH": self.db, "TESTING": True})

    def test_boot_recusado_sem_alterar_o_banco(self):
        antes, arquivos = sha256(self.db), self.arquivos()
        for seed in (True, False):
            with self.subTest(seed=seed), self.assertRaises(database.MigracaoPendenteError) as ctx:
                create_app({"DATABASE_PATH": self.db, "SEED_ON_STARTUP": seed, "TESTING": True,
                            "SEED_SENHAS": {"admin@loja.com": "x"}})
            self.assertIn("3 credencial(is) legada(s)", str(ctx.exception))
            self.assertNotIn(self.marca, str(ctx.exception))
        self.assertEqual((sha256(self.db), self.arquivos()), (antes, arquivos))

    def test_banco_novo_e_banco_so_com_hashes_iniciam(self):
        novo = os.path.join(self.tmp.name, "novo.db")
        create_app({"DATABASE_PATH": novo, "TESTING": True})
        so_hash = os.path.join(self.tmp.name, "hash.db")
        criar_banco(so_hash, [u for u in self.usuarios if usuario.hash_preservavel(u[2]) or u[2] is None])
        antes = dump(so_hash)
        create_app({"DATABASE_PATH": so_hash, "TESTING": True})
        self.assertEqual(dump(so_hash), antes)

    def test_simulacao_nao_grava(self):
        antes, mtime, arquivos = sha256(self.db), os.stat(self.db).st_mtime_ns, self.arquivos()
        codigo, saida = self.migrar()
        self.assertEqual(codigo, 0)
        self.assertIn("legadas=3", saida)
        self.assertIn("Nenhuma alteração foi gravada", saida)
        self.assertNotIn(self.marca, saida)
        self.assertEqual((sha256(self.db), os.stat(self.db).st_mtime_ns, self.arquivos()), (antes, mtime, arquivos))

    def test_aplicar_invalida_legadas_e_preserva_o_resto(self):
        antes = dump(self.db)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 0, saida)
        self.assertNotIn(self.marca, saida)
        depois = dump(self.db)
        for tabela in ("produtos", "pedidos", "itens_pedido"):
            self.assertEqual(depois[tabela], antes[tabela])
        esperado = [row[:3] + ((None,) if row[0] in (1, 3, 6) else (row[3],)) + row[4:] for row in antes["usuarios"]]
        self.assertEqual(depois["usuarios"], esperado, "IDs, nomes, e-mails, perfis e datas preservados")
        self.assertEqual(self.arquivos(), ["loja.db"], "sem journal/WAL remanescente")
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(self.bytes_contem(self.marca), {"loja.db": False})
        self.assertEqual(self.bytes_contem("abc$def$ghi"), {"loja.db": False})
        # Boot aceito; hashes válidos autenticam; legadas não.
        client = create_app({"DATABASE_PATH": self.db, "TESTING": True}).test_client()
        self.assertEqual(client.post("/login", json={"email": "hash@x", "senha": self.senha_hash}).status_code, 200)
        self.assertEqual(client.post("/login", json={"email": "pbkdf2@x", "senha": self.senha_hash}).status_code, 200)
        for email, senha in (("legado@x", self.marca), ("formato@x", "abc$def$ghi")):
            self.assertEqual(client.post("/login", json={"email": email, "senha": senha}).status_code, 401)
        # Segunda execução: nada a alterar.
        antes_2 = dump(self.db)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 0)
        self.assertIn("0 credencial(is) invalidada(s)", saida)
        self.assertEqual(dump(self.db), antes_2)

    def test_falha_antes_do_commit_desfaz_tudo(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TRIGGER falha BEFORE UPDATE OF senha ON usuarios WHEN OLD.id = 3 "
                    "BEGIN SELECT RAISE(ABORT, 'falha induzida'); END")
        con.commit()
        con.close()
        antes, arquivos = sha256(self.db), self.arquivos()
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 1)
        self.assertIn("Transação desfeita", saida)
        self.assertEqual((sha256(self.db), self.arquivos()), (antes, arquivos))
        with self.assertRaises(database.MigracaoPendenteError):
            create_app({"DATABASE_PATH": self.db, "TESTING": True})

    def test_falha_na_limpeza_e_retomada(self):
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA secure_delete = OFF")  # simula um build sem secure_delete: deixa sobra no arquivo
        con.execute("UPDATE usuarios SET senha = ? WHERE id = 1", (self.marca + "-nova",))
        con.commit()
        con.close()
        self.assertTrue(self.bytes_contem(self.marca)["loja.db"], "sobra da senha antiga presente antes")

        def falhar(_con):
            raise sqlite3.OperationalError("falha induzida na limpeza")

        with mock.patch.object(migrar_senhas, "limpar", falhar):
            codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 1)
        self.assertIn("execute novamente com --aplicar", saida)
        self.assertEqual(dump(self.db)["usuarios"][0][3], None, "etapa 1 já confirmada")
        # Com a limpeza pendente, o boot continua recusado e a simulação informa.
        antes = sha256(self.db)
        with self.assertRaises(database.MigracaoPendenteError) as ctx:
            create_app({"DATABASE_PATH": self.db, "TESTING": True})
        self.assertIn("limpeza física", str(ctx.exception))
        self.assertEqual(sha256(self.db), antes)
        self.assertIn("limpeza_pendente=sim", self.migrar()[1])
        codigo, saida = self.migrar("--aplicar")  # retomada
        self.assertEqual(codigo, 0, saida)
        self.assertIn("limpeza_pendente=não", saida.splitlines()[-1])
        self.assertEqual(self.bytes_contem(self.marca), {"loja.db": False})
        self.assertEqual(self.arquivos(), ["loja.db"])
        create_app({"DATABASE_PATH": self.db, "TESTING": True})  # boot aceito

    def test_user_version_inesperado_nao_e_alterado(self):
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA user_version = 7")
        con.commit()
        con.close()
        antes = sha256(self.db)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 1)
        self.assertIn("user_version inesperado", saida)
        self.assertEqual(sha256(self.db), antes)

    def test_banco_precisa_existir(self):
        inexistente = os.path.join(self.tmp.name, "nao_existe.db")
        for args in ([inexistente], [inexistente, "--aplicar"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(migrar_senhas.main(args), 2)
        self.assertFalse(os.path.exists(inexistente))


class PreservacaoHashesValidosTest(unittest.TestCase):
    """Revisão 2: hashes válidos do Werkzeug (pbkdf2:sha512_256, pbkdf2:sha512_224, scrypt com salt de
    129 caracteres) são preservados no boot, na simulação e no --aplicar, e continuam autenticando."""

    METODOS = [("sha512_256@x", {"method": "pbkdf2:sha512_256:600000"}, "admin"),
               ("sha512_224@x", {"method": "pbkdf2:sha512_224:600000"}, "cliente"),
               ("salt129@x", {"method": "scrypt", "salt_length": 129}, "cliente")]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "loja.db")
        self.senhas = {email: "SENHA-" + secrets.token_hex(8) for email, _, _ in self.METODOS}
        self.hashes = {email: generate_password_hash(self.senhas[email], **kwargs) for email, kwargs, _ in self.METODOS}
        self.marca = "LEGADO-" + secrets.token_hex(8)

    def tearDown(self):
        self.tmp.cleanup()

    def criar(self, com_legados):
        usuarios = [("Hash", email, self.hashes[email], perfil) for email, _, perfil in self.METODOS]
        if com_legados:
            usuarios += [("Legado", "legado@x", self.marca, "admin"), ("Gigante", "gigante@x", GIGANTE, "cliente")]
        criar_banco(self.db, usuarios + [("Sem credencial", "nulo@x", None, "cliente")])

    def migrar(self, *args):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = migrar_senhas.main([self.db, *args])
        return codigo, saida.getvalue()

    def estado(self):
        resultado = {}
        for nome in sorted(os.listdir(self.tmp.name)):
            with open(os.path.join(self.tmp.name, nome), "rb") as fh:
                resultado[nome] = hashlib.sha256(fh.read()).hexdigest()
        return resultado

    def logins(self, client, extras=()):
        credenciais = list(self.senhas.items()) + list(extras)
        return {email: client.post("/login", json={"email": email, "senha": senha}).status_code
                for email, senha in credenciais}

    def test_login_e_classificacao_concordam(self):
        for email in self.hashes:
            with self.subTest(email=email):
                self.assertTrue(usuario._senha_confere(self.hashes[email], self.senhas[email]))
                self.assertTrue(usuario.hash_preservavel(self.hashes[email]))

    def test_banco_so_com_hashes_validos_inicia_e_simulacao_nao_conta_legadas(self):
        self.criar(com_legados=False)
        antes, dados = self.estado(), dump(self.db)
        codigo, saida = self.migrar()
        self.assertEqual(codigo, 0, saida)
        self.assertIn("hashes_validos=3", saida)
        self.assertIn("legadas=0", saida)
        self.assertEqual(self.estado(), antes)
        client = create_app({"DATABASE_PATH": self.db, "TESTING": True, "SEED_ON_STARTUP": False}).test_client()
        self.assertEqual(self.logins(client), dict.fromkeys(self.senhas, 200))
        self.assertEqual(dump(self.db), dados)

    def test_banco_misto_invalida_somente_as_legadas(self):
        self.criar(com_legados=True)
        dados = dump(self.db)
        with self.assertRaises(database.MigracaoPendenteError) as ctx:
            create_app({"DATABASE_PATH": self.db, "TESTING": True})
        self.assertIn("2 credencial(is) legada(s)", str(ctx.exception))
        codigo, saida = self.migrar()
        self.assertEqual((codigo, "legadas=2" in saida, "hashes_validos=3" in saida), (0, True, True), saida)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 0, saida)
        self.assertIn("2 credencial(is) invalidada(s)", saida)
        depois = dump(self.db)
        for tabela in ("produtos", "pedidos", "itens_pedido"):
            self.assertEqual(depois[tabela], dados[tabela])
        legados = {"legado@x", "gigante@x"}
        esperado = [row[:3] + ((None,) if row[2] in legados else (row[3],)) + row[4:] for row in dados["usuarios"]]
        self.assertEqual(depois["usuarios"], esperado, "IDs, nomes, e-mails, perfis e datas preservados")
        senhas = {row[2]: row[3] for row in depois["usuarios"]}
        self.assertEqual({e: senhas[e] for e in self.hashes}, self.hashes, "hashes válidos idênticos")
        client = create_app({"DATABASE_PATH": self.db, "TESTING": True, "SEED_ON_STARTUP": False}).test_client()
        self.assertEqual(self.logins(client, [("legado@x", self.marca)]),
                         dict(dict.fromkeys(self.senhas, 200), **{"legado@x": 401}))
        perfis = {e: client.post("/login", json={"email": e, "senha": s}).get_json()["dados"]["tipo"]
                  for e, s in self.senhas.items()}
        self.assertEqual(perfis, {email: perfil for email, _, perfil in self.METODOS})


FILHO = r"""
import sqlite3, sys
modo, db, senha = sys.argv[1:]
con = sqlite3.connect(db, isolation_level=None)
if modo == "leitor":
    con.execute("BEGIN")
    con.execute("SELECT id, senha FROM usuarios").fetchall()
else:  # escritor: commit que fica só no WAL, com a conexão aberta
    con.execute("PRAGMA wal_autocheckpoint = 0")
    con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Novo', 'novo@x', ?, 'cliente')", (senha,))
print("pronto", flush=True)
sys.stdin.readline()
if con.in_transaction:
    con.execute("ROLLBACK")
con.close()
"""


class WalESimulacaoTest(unittest.TestCase):
    """Banco em WAL: limpeza comprovada antes de liberar o boot e simulação sem tocar nos arquivos.

    As conexões concorrentes ficam em outro processo: no POSIX, fechar qualquer descritor de um
    arquivo libera os locks fcntl do processo sobre ele, o que desfaria um leitor deste processo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "loja.db")
        self.marca = "LEGADO-" + secrets.token_hex(8)
        self.senha = secrets.token_urlsafe(12)
        self.hash = generate_password_hash(self.senha)
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA journal_mode = WAL")
        for comando in database.SCHEMA:
            con.execute(comando)
        con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
                        [("Hash", "hash@x", self.hash, "admin"), ("Legado", "legado@x", self.marca, "cliente")])
        con.commit()
        self.con = con  # mantém o WAL até o filho abrir a própria conexão

    def tearDown(self):
        if self.con:
            self.con.close()
        self.tmp.cleanup()

    def filho(self, modo, senha=""):
        proc = subprocess.Popen([sys.executable, "-B", "-c", FILHO, modo, self.db, senha],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(proc.stdout.readline().strip(), "pronto")
        self.con.close()
        self.con = None
        return proc

    def encerrar(self, proc):
        proc.stdin.write("\n")
        proc.stdin.close()
        proc.wait(30)
        proc.stdout.close()

    def estado(self):
        resultado = {}
        for nome in sorted(os.listdir(self.tmp.name)):
            with open(os.path.join(self.tmp.name, nome), "rb") as fh:
                resultado[nome] = hashlib.sha256(fh.read()).hexdigest()
        return resultado

    def ocorrencias(self):
        total = 0
        for nome in os.listdir(self.tmp.name):
            with open(os.path.join(self.tmp.name, nome), "rb") as fh:
                total += fh.read().count(self.marca.encode())
        return total

    def migrar(self, *args):
        r = subprocess.run([sys.executable, "-B", "migrar_senhas.py", self.db, *args], cwd=PROJECT_ROOT,
                           capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def senhas(self):
        con = sqlite3.connect(self.db)
        try:
            return dict(con.execute("SELECT email, senha FROM usuarios")), con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()

    def test_leitor_aberto_falha_controlada_e_retomada(self):
        leitor = self.filho("leitor")
        self.assertGreater(self.ocorrencias(), 0)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 1, saida)
        self.assertIn("Limpeza física não comprovada", saida)
        self.assertNotIn("Traceback", saida)
        senhas, versao = self.senhas()
        self.assertEqual((senhas["legado@x"], senhas["hash@x"], versao), (None, self.hash, usuario.LIMPEZA_PENDENTE))
        with self.assertRaises(database.MigracaoPendenteError):
            create_app({"DATABASE_PATH": self.db, "TESTING": True})
        self.encerrar(leitor)
        codigo, saida = self.migrar("--aplicar")
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(self.ocorrencias(), 0)
        senhas, versao = self.senhas()
        self.assertEqual((senhas["legado@x"], senhas["hash@x"], versao), (None, self.hash, 0))
        client = create_app({"DATABASE_PATH": self.db, "TESTING": True, "SEED_ON_STARTUP": False}).test_client()
        self.assertEqual(client.post("/login", json={"email": "hash@x", "senha": self.senha}).status_code, 200)

    def test_simulacao_wal_fechado_sem_auxiliares(self):
        self.con.close()
        self.con = None
        antes = self.estado()
        self.assertEqual(list(antes), ["loja.db"])
        codigo, saida = self.migrar()
        self.assertEqual((codigo, "legadas=1" in saida, "journal_mode=wal" in saida), (0, True, True), saida)
        self.assertEqual(self.estado(), antes)

    def test_simulacao_considera_dados_confirmados_no_wal(self):
        self.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        escritor = self.filho("escritor", "LEGADO-SO-NO-WAL")
        try:
            antes = self.estado()
            self.assertEqual(sorted(antes), ["loja.db", "loja.db-shm", "loja.db-wal"])
            codigo, saida = self.migrar()
            self.assertEqual((codigo, "usuarios=3" in saida, "legadas=2" in saida), (0, True, True), saida)
            self.assertEqual(self.estado(), antes)
        finally:
            self.encerrar(escritor)

    def test_simulacao_recusa_journal_ativo(self):
        self.con.close()
        self.con = None
        with open(self.db + "-journal", "wb") as fh:
            fh.write(migrar_senhas.MAGIC_JOURNAL + bytes(504))
        antes = self.estado()
        codigo, saida = self.migrar()
        self.assertEqual(codigo, 1)
        self.assertIn("Simulação recusada", saida)
        self.assertEqual(self.estado(), antes)


if __name__ == "__main__":
    unittest.main()
