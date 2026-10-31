import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class DomainError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, extra=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.extra = extra or {}


class ValidationError(DomainError):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


def register_error_handlers(app):
    @app.errorhandler(DomainError)
    def handle_domain_error(error):
        return jsonify({"erro": error.message, **error.extra}), error.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Rotas inexistentes e métodos não permitidos mantêm a resposta padrão do Flask.
        if isinstance(error, HTTPException):
            return error
        logger.exception("Erro não tratado")
        return jsonify({"erro": "Erro interno do servidor"}), 500
