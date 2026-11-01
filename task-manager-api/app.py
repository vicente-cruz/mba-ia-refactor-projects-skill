"""Ponto de entrada. Importar este módulo não lê o ambiente nem cria arquivos.

Uso: SECRET_KEY=... python app.py   (variáveis em .env.example)
"""
import logging
import sys

from flask import Flask
from flask_cors import CORS

from config import ConfigError, load_config
from database import db, init_schema
from errors import register_error_handlers
from routes.category_routes import category_bp
from routes.report_routes import report_bp
from routes.system_routes import system_bp
from routes.task_routes import task_bp
from routes.user_routes import user_bp

BLUEPRINTS = (system_bp, task_bp, user_bp, report_bp, category_bp)


def _configure_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


def create_app(overrides=None):
    """Valida a configuração antes de tocar no banco; depois prepara schema, handlers e rotas."""
    config = load_config(overrides)
    app = Flask(__name__)
    app.config.update(config)
    _configure_logging()
    CORS(app, origins=config['CORS_ORIGINS'])
    db.init_app(app)
    with app.app_context():
        init_schema()
    register_error_handlers(app)
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app


def main():
    try:
        app = create_app()
    except ConfigError as error:
        print(f'Erro de configuração: {error}', file=sys.stderr)
        return 2
    except Exception as error:  # falha ao preparar o schema
        print(f'Falha ao inicializar a aplicação ({type(error).__name__})', file=sys.stderr)
        return 1
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config['PORT'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
