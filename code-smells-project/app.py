import logging
import sys

from flask import Flask
from flask_cors import CORS

import database
from config import ConfigError, load_config, validate_config
from errors import register_error_handlers
from routes.pedidos import pedidos_bp
from routes.produtos import produtos_bp
from routes.relatorios import relatorios_bp
from routes.sistema import sistema_bp
from routes.usuarios import usuarios_bp

logger = logging.getLogger(__name__)


def create_app(overrides=None, *, connection_factory=None):
    """Composition root. `connection_factory` substitui a abertura de DATABASE_PATH nesta instância.

    A configuração é lida e validada antes de qualquer acesso ao banco (ConfigError).
    """
    config = load_config()
    if overrides:
        config.update(overrides)
    validate_config(config)

    app = Flask(__name__)
    app.config.from_mapping(config)
    CORS(app)
    database.init_app(app, connection_factory)
    database.prepare(app)
    register_error_handlers(app)
    for blueprint in (produtos_bp, usuarios_bp, pedidos_bp, relatorios_bp, sistema_bp):
        app.register_blueprint(blueprint)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        app = create_app()
    except ConfigError as erro:
        logger.error("Inicialização recusada: %s", erro)
        sys.exit(1)
    host, port = app.config["HOST"], app.config["PORT"]
    print("=" * 50)
    print("SERVIDOR INICIADO")
    print(f"Rodando em http://{host}:{port}")
    print("=" * 50)
    app.run(host=host, port=port, debug=app.config["DEBUG"])
