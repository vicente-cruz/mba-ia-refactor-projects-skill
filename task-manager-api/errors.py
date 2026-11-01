"""Exceções de domínio e handlers centralizados. Formato de erro: {'error': <mensagem>}."""
import logging

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger('task_manager')

INVALID_BODY_MESSAGE = 'Dados inválidos'
INTERNAL_ERROR_MESSAGE = 'Erro interno'
HTTP_MESSAGES = {
    400: INVALID_BODY_MESSAGE,
    404: 'Recurso não encontrado',
    405: 'Método não permitido',
    415: INVALID_BODY_MESSAGE,
}


class AppError(Exception):
    status_code = 500

    def __init__(self, message, headers=None):
        super().__init__(message)
        self.message = message
        self.headers = headers or {}


class ValidationError(AppError):
    status_code = 400


class AuthError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class OperationError(AppError):
    """Falha de persistência: 500 com a mensagem da operação (ex.: 'Erro ao atualizar')."""
    status_code = 500


def _error_response(message, status, headers=None):
    response = jsonify({'error': message})
    response.status_code = status
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def register_error_handlers(app):
    from database import db

    @app.errorhandler(AppError)
    def handle_app_error(error):
        return _error_response(error.message, error.status_code, error.headers)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        message = HTTP_MESSAGES.get(error.code, error.name)
        # Preserva cabeçalhos do framework (ex.: Allow no 405), exceto os do corpo HTML.
        headers = {key: value for key, value in error.get_headers()
                   if key.lower() not in ('content-type', 'content-length')}
        return _error_response(message, error.code, headers)

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        db.session.rollback()
        logger.exception('Erro inesperado em %s %s', request.method, request.path)
        return _error_response(INTERNAL_ERROR_MESSAGE, 500)
