import logging

from flask import Flask
from flask_cors import CORS

import database
from config import load_config
from errors import register_error_handlers
from routes.pedidos import pedidos_bp
from routes.produtos import produtos_bp
from routes.relatorios import relatorios_bp
from routes.sistema import sistema_bp
from routes.usuarios import usuarios_bp


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if overrides:
        app.config.update(overrides)
    CORS(app)
    database.init_app(app)
    database.init_db(app)
    register_error_handlers(app)
    for blueprint in (produtos_bp, usuarios_bp, pedidos_bp, relatorios_bp, sistema_bp):
        app.register_blueprint(blueprint)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    host, port = app.config["HOST"], app.config["PORT"]
    print("=" * 50)
    print("SERVIDOR INICIADO")
    print(f"Rodando em http://{host}:{port}")
    print("=" * 50)
    app.run(host=host, port=port, debug=app.config["DEBUG"])
