"""Testes de regressão das falhas corrigidas na revisão (números não finitos,
tipo de consulta administrativa, senhas legadas/hashes malformados e importação).

Executar a partir da raiz do projeto, sem dependências além de requirements.txt:
    python -B -m unittest discover -s tests -v
"""
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

PRODUTO_VALIDO = '{{"nome": "Produto X", "preco": {preco}, "estoque": {estoque}, "categoria": "geral"}}'
NAO_FINITOS = ["1e309", "-1e309", "NaN", "Infinity", "-Infinity"]


class BaseApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "loja.db")
        self.token = secrets.token_urlsafe(16)
        self.senha_admin = secrets.token_urlsafe(16)
        self.app = create_app({
            "DATABASE_PATH": self.db_path,
            "ADMIN_TOKEN": self.token,
            "SEED_SENHAS": {"admin@loja.com": self.senha_admin},
            "TESTING": True,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def query(self, sql, params=()):
        con = sqlite3.connect(self.db_path)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()

    def produtos(self):
        return self.query("SELECT id, nome, descricao, preco, estoque, categoria FROM produtos ORDER BY id")

    def post_json(self, caminho, corpo, **kwargs):
        return self.client.post(caminho, data=corpo, content_type="application/json", **kwargs)


class NumerosNaoFinitosTest(BaseApiTest):
    def test_criacao_rejeita_preco_nao_finito_sem_gravar(self):
        antes = self.produtos()
        for valor in NAO_FINITOS:
            with self.subTest(preco=valor):
                resp = self.post_json("/produtos", PRODUTO_VALIDO.format(preco=valor, estoque=1))
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(), {"erro": "Preço inválido"})
        self.assertEqual(self.produtos(), antes)

    def test_criacao_rejeita_estoque_nao_finito_sem_gravar(self):
        antes = self.produtos()
        for valor in NAO_FINITOS:
            with self.subTest(estoque=valor):
                resp = self.post_json("/produtos", PRODUTO_VALIDO.format(preco=1, estoque=valor))
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(), {"erro": "Estoque inválido"})
        self.assertEqual(self.produtos(), antes)

    def test_atualizacao_rejeita_nao_finitos_sem_alterar(self):
        antes = self.produtos()
        for campo, corpo in [("preco", PRODUTO_VALIDO.format(preco="{v}", estoque=1)),
                             ("estoque", PRODUTO_VALIDO.format(preco=1, estoque="{v}"))]:
            for valor in NAO_FINITOS:
                with self.subTest(campo=campo, valor=valor):
                    resp = self.client.put("/produtos/1", data=corpo.replace("{v}", valor),
                                           content_type="application/json")
                    self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.produtos(), antes)

    def test_valores_finitos_continuam_aceitos(self):
        for preco, estoque in [("0", "0"), ("12.5", "3"), ("1e6", "2.0"), ("5999.99", "10")]:
            with self.subTest(preco=preco, estoque=estoque):
                resp = self.post_json("/produtos", PRODUTO_VALIDO.format(preco=preco, estoque=estoque))
                self.assertEqual(resp.status_code, 201)
                produto_id = resp.get_json()["dados"]["id"]
                gravado = self.query("SELECT preco, estoque FROM produtos WHERE id = ?", (produto_id,))[0]
                self.assertEqual(gravado, (float(preco), float(estoque)))
        resp = self.client.put("/produtos/1", data=PRODUTO_VALIDO.format(preco="7.25", estoque="4"),
                               content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.query("SELECT preco, estoque FROM produtos WHERE id = 1")[0], (7.25, 4))

    def test_filtros_de_busca_rejeitam_nao_finitos(self):
        for parametro in ("preco_min", "preco_max"):
            for valor in ("inf", "-inf", "nan", "NaN", "Infinity", "1e309"):
                with self.subTest(parametro=parametro, valor=valor):
                    resp = self.client.get(f"/produtos/busca?{parametro}={valor}")
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(resp.get_json(), {"erro": f"Parâmetro {parametro} inválido"})

    def test_filtros_finitos_continuam_funcionando(self):
        resp = self.client.get("/produtos/busca?preco_min=100&preco_max=300")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([p["nome"] for p in resp.get_json()["dados"]],
                         ["Teclado Mecânico", "Headset Gamer", "Webcam HD"])


class TipoConsultaAdministrativaTest(BaseApiTest):
    def admin_query(self, corpo, token=True):
        headers = {"X-Admin-Token": self.token} if token else {}
        return self.post_json("/admin/query", corpo, headers=headers)

    def test_tipos_invalidos_retornam_400(self):
        for corpo in ('{"consulta": ["contagem_por_tabela"]}', '{"consulta": {"nome": "contagem_por_tabela"}}',
                      '{"consulta": 1}', '{"consulta": true}', '{"consulta": 1.5}'):
            with self.subTest(corpo=corpo):
                resp = self.admin_query(corpo)
                self.assertEqual(resp.status_code, 400)
                self.assertTrue(resp.get_json()["erro"].startswith("Consulta inválida. Válidas: "))

    def test_vazios_continuam_como_consulta_nao_informada(self):
        for corpo in ('{"consulta": []}', '{"consulta": {}}', '{"consulta": ""}', '{"consulta": null}', "{}"):
            with self.subTest(corpo=corpo):
                resp = self.admin_query(corpo)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json(), {"erro": "Consulta não informada"})

    def test_autorizacao_continua_antes_da_validacao(self):
        resp = self.admin_query('{"consulta": ["contagem_por_tabela"]}', token=False)
        self.assertEqual(resp.status_code, 401)
        self.app.config["ADMIN_TOKEN"] = None
        resp = self.admin_query('{"consulta": ["contagem_por_tabela"]}')
        self.assertEqual(resp.status_code, 403)

    def test_consulta_valida_continua_funcionando(self):
        resp = self.admin_query('{"consulta": "contagem_por_tabela"}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["dados"][0], {"tabela": "produtos", "quantidade": 10})


class SenhasLegadasTest(BaseApiTest):
    LEGADOS = [
        ("legado1@loja.com", "abc$def$ghi"),             # texto puro com "$": método 'abc' inválido
        ("legado2@loja.com", "texto-puro"),              # texto puro sem "$"
        ("legado3@loja.com", "pbkdf2:sha256:abc$s$h"),   # iterações não numéricas
        ("legado4@loja.com", "pbkdf2:nada:10$s$h"),      # digest não suportado
        ("legado5@loja.com", "scrypt:x:8:1$s$h"),        # parâmetros scrypt inválidos
        ("legado6@loja.com", ""),                        # vazio
        # Rodada 3 — formatos que ainda provocavam 500 (revisão independente):
        ("legado7@loja.com", "pbkdf2:sha256:1000$salt$á"),                         # hash não ASCII (TypeError)
        ("legado8@loja.com", "pbkdf2:sha256:999999999999999999999$salt$hash"),     # iterações > C long (OverflowError)
        ("legado9@loja.com", "scrypt:32768:8:-1$salt$hash"),                       # p negativo (TypeError/ValueError)
        ("legado10@loja.com", "scrypt:9999999999:9999999999:9999999999$salt$00"),  # parâmetros > C long (OverflowError)
        ("legado11@loja.com", "pbkdf2:sha256:1000$salt$ÿ"),                        # hash não ASCII (TypeError)
    ]

    def setUp(self):
        super().setUp()
        con = sqlite3.connect(self.db_path)
        con.executemany("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Legado', ?, ?, 'cliente')",
                        self.LEGADOS)
        con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Nulo', 'nulo@loja.com', NULL, 'cliente')")
        con.commit()
        con.close()

    def usuarios(self):
        return self.query("SELECT id, nome, email, senha, tipo FROM usuarios ORDER BY id")

    def login(self, email, senha):
        return self.client.post("/login", json={"email": email, "senha": senha})

    def test_legados_e_malformados_retornam_401_sem_modificar_banco(self):
        antes = self.usuarios()
        for email, senha in self.LEGADOS + [("nulo@loja.com", None)]:
            for tentativa in filter(None, [senha, "outra-senha"]):
                with self.subTest(email=email, tentativa=tentativa):
                    resp = self.login(email, tentativa)
                    self.assertEqual(resp.status_code, 401)
                    self.assertEqual(resp.get_json(), {"erro": "Email ou senha inválidos", "sucesso": False})
        self.assertEqual(self.usuarios(), antes)

    def test_hashes_validos_continuam_autenticando(self):
        self.assertEqual(self.login("admin@loja.com", self.senha_admin).status_code, 200)
        self.assertEqual(self.login("admin@loja.com", "errada").status_code, 401)
        for metodo in ("scrypt", "pbkdf2:sha256", "pbkdf2:sha256:1000"):
            with self.subTest(metodo=metodo):
                email = f"{metodo.replace(':', '-')}@loja.com"
                con = sqlite3.connect(self.db_path)
                con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Hash', ?, ?, 'cliente')",
                            (email, generate_password_hash("senha-correta", method=metodo)))
                con.commit()
                con.close()
                self.assertEqual(self.login(email, "senha-correta").status_code, 200)
                self.assertEqual(self.login(email, "senha-errada").status_code, 401)

    def test_cadastro_duplicado_com_hash_valido_apos_legado_autentica(self):
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO usuarios (nome, email, senha, tipo) VALUES ('Novo', 'legado1@loja.com', ?, 'cliente')",
                    (generate_password_hash("nova-senha"),))
        con.commit()
        con.close()
        resp = self.login("legado1@loja.com", "nova-senha")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["dados"]["nome"], "Novo")

    def test_erro_de_infraestrutura_nao_e_mascarado_como_401(self):
        con = sqlite3.connect(self.db_path)
        con.execute("ALTER TABLE usuarios RENAME TO usuarios_x")
        con.commit()
        con.close()
        resp = self.login("admin@loja.com", self.senha_admin)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json(), {"erro": "Erro interno do servidor"})


class FormatoHashTest(unittest.TestCase):
    """O tipo da exceção do hashlib varia com a versão do Python/OpenSSL (ex.: p negativo no scrypt dá
    TypeError em um ambiente e ValueError em outro); formatos inválidos não podem chegar a ele."""

    # legado10 (parâmetros enormes) tem estrutura válida: chega ao hashlib e é recusado via OverflowError,
    # coberto pelo teste de login em SenhasLegadasTest.
    INVALIDOS = [valor for email, valor in SenhasLegadasTest.LEGADOS if email != "legado10@loja.com"] + [
        "scrypt:32768:8:1$sál$00", "scrypt$salt$00", "pbkdf2$salt$00", "pbkdf2:sha256:1000$salt$00\n"]

    def test_hashes_gerados_pelo_werkzeug_tem_formato_aceito(self):
        from models.usuario import FORMATO_HASH
        for metodo in ("scrypt", "pbkdf2", "pbkdf2:sha256", "pbkdf2:sha256:1000", "pbkdf2:sha512:600000"):
            with self.subTest(metodo=metodo):
                self.assertIsNotNone(FORMATO_HASH.fullmatch(generate_password_hash("x", method=metodo)))

    def test_formato_invalido_nao_chega_ao_check_password_hash(self):
        from unittest import mock
        from models import usuario
        with mock.patch.object(usuario, "check_password_hash",
                               side_effect=TypeError("p is required and must be an unsigned int")) as check:
            for valor in self.INVALIDOS:
                with self.subTest(valor=valor):
                    self.assertFalse(usuario._senha_confere(valor, "qualquer"))
            check.assert_not_called()

    def test_typeerror_fora_da_validacao_de_formato_nao_e_mascarado(self):
        # A captura é restrita a ValueError/OverflowError: um TypeError inesperado com formato válido propaga.
        from unittest import mock
        from models import usuario
        with mock.patch.object(usuario, "check_password_hash", side_effect=TypeError("inesperado")):
            with self.assertRaises(TypeError):
                usuario._senha_confere(generate_password_hash("x"), "x")


class ImportacaoTest(unittest.TestCase):
    def test_importar_app_nao_cria_banco(self):
        with tempfile.TemporaryDirectory() as cwd:
            antes_projeto = set(os.listdir(PROJECT_ROOT))
            codigo = f"import sys; sys.path.insert(0, {PROJECT_ROOT!r}); import app; print(app.__file__)"
            env = {k: v for k, v in os.environ.items() if k != "DATABASE_PATH"}
            resultado = subprocess.run([sys.executable, "-I", "-B", "-c", codigo], cwd=cwd, env=env,
                                       capture_output=True, text=True, timeout=30)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertEqual(resultado.stdout.strip(), os.path.join(PROJECT_ROOT, "app.py"))
            self.assertEqual(os.listdir(cwd), [])
            self.assertEqual(set(os.listdir(PROJECT_ROOT)), antes_projeto)


if __name__ == "__main__":
    unittest.main()
