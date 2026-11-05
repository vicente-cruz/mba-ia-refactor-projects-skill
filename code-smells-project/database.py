import logging
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

FACTORY_KEY = "loja.db_factory"

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        preco REAL,
        estoque INTEGER,
        categoria TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT,
        senha TEXT,
        tipo TEXT DEFAULT 'cliente',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        status TEXT DEFAULT 'pendente',
        total REAL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER,
        produto_id INTEGER,
        quantidade INTEGER,
        preco_unitario REAL
    )
    """,
]

PRODUTOS_SEED = [
    ("Notebook Gamer", "Notebook potente para jogos", 5999.99, 10, "informatica"),
    ("Mouse Wireless", "Mouse sem fio ergonômico", 89.90, 50, "informatica"),
    ("Teclado Mecânico", "Teclado mecânico RGB", 299.90, 30, "informatica"),
    ("Monitor 27''", "Monitor 27 polegadas 144hz", 1899.90, 15, "informatica"),
    ("Headset Gamer", "Headset com microfone", 199.90, 25, "informatica"),
    ("Cadeira Gamer", "Cadeira ergonômica", 1299.90, 8, "moveis"),
    ("Webcam HD", "Webcam 1080p", 249.90, 20, "informatica"),
    ("Hub USB", "Hub USB 3.0 7 portas", 79.90, 40, "informatica"),
    ("SSD 1TB", "SSD NVMe 1TB", 449.90, 35, "informatica"),
    ("Camiseta Dev", "Camiseta estampa código", 59.90, 100, "vestuario"),
]

# Senhas dos usuários de demonstração vêm da configuração (SEED_SENHAS).
USUARIOS_SEED = [
    ("Admin", "admin@loja.com", "admin"),
    ("João Silva", "joao@email.com", "cliente"),
    ("Maria Santos", "maria@email.com", "cliente"),
]


def connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_app(app, connection_factory=None):
    """Registra a fábrica de conexões da instância. Sem fábrica injetada, abre DATABASE_PATH.

    A fábrica deve devolver uma conexão sqlite3 com row_factory = sqlite3.Row; ela é aberta uma vez
    por contexto da aplicação (get_db) e fechada no teardown.
    """
    if connection_factory is None:
        def connection_factory():
            return connect(app.config["DATABASE_PATH"])
    app.extensions[FACTORY_KEY] = connection_factory
    app.teardown_appcontext(close_db)


def get_db():
    if "db" not in g:
        g.db = current_app.extensions[FACTORY_KEY]()
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(db):
    """Prepara apenas a estrutura das tabelas; não insere dados."""
    with db:
        for statement in SCHEMA:
            db.execute(statement)


def seed_demo_if_empty(db, senhas):
    """Carga de demonstração numa transação única.

    Mantém a condição histórica (só quando `produtos` está vazia). Usuários de demonstração cujo
    e-mail já existe são pulados, preservando senha e perfil existentes (D-7 b).
    """
    if db.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] != 0:
        return False
    with db:
        db.executemany(
            "INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)",
            PRODUTOS_SEED,
        )
        for nome, email, tipo in USUARIOS_SEED:
            if db.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone():
                logger.info("Usuário de demonstração %s já existe; mantido sem alteração.", email)
                continue
            senha = senhas.get(email)
            if not senha:
                logger.warning("Senha de seed não configurada para %s; usuário de demonstração não criado.", email)
                continue
            db.execute(
                "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
                (nome, email, generate_password_hash(senha), tipo),
            )
    return True


def prepare(app):
    """Inicialização explícita: sempre prepara as tabelas; o seed depende de SEED_ON_STARTUP."""
    with app.app_context():
        db = get_db()
        init_schema(db)
        if app.config["SEED_ON_STARTUP"]:
            seed_demo_if_empty(db, app.config.get("SEED_SENHAS", {}))
        else:
            logger.info("SEED_ON_STARTUP=0: carga de demonstração desligada.")
