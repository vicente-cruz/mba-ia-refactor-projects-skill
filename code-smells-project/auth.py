import hmac
from functools import wraps

from flask import current_app, request

from errors import DomainError


def require_admin_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("ADMIN_TOKEN")
        if not expected:
            raise DomainError("Operação administrativa desabilitada", 403)
        provided = request.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(provided.encode(), expected.encode()):
            raise DomainError("Não autorizado", 401)
        return view(*args, **kwargs)

    return wrapper
