"""Token assinado (itsdangerous) vinculado à instância da conta pelo auth_nonce.

Não é JWT nem é criptografado: o payload {"uid", "sid"} é legível e só leva o ID
e o nonce aleatório da conta. Senha e hash nunca entram no token.
"""
import hmac
import re

from flask import current_app, request
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from errors import AuthError, ForbiddenError
from models.user import User

TOKEN_SALT = 'task-manager-auth'
TOKEN_MAX_LENGTH = 4096
NONCE_PATTERN = re.compile(r'^[A-Za-z0-9_-]{43}$')
PAYLOAD_KEYS = {'uid', 'sid'}

MISSING_TOKEN = 'Token ausente'
INVALID_TOKEN = 'Token inválido'
EXPIRED_TOKEN = 'Token expirado'
INACTIVE_USER = 'Usuário inativo'
PERMISSION_DENIED = 'Permissão negada'


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=TOKEN_SALT)


def issue_token(user):
    return _serializer().dumps({'uid': user.id, 'sid': user.auth_nonce})


def _extract_token(header_value):
    parts = header_value.split(' ')
    if len(parts) != 2 or parts[0].lower() != 'bearer' or not parts[1]:
        raise AuthError(INVALID_TOKEN)
    token = parts[1]
    if len(token) > TOKEN_MAX_LENGTH:
        raise AuthError(INVALID_TOKEN)
    return token


def _load_payload(token):
    try:
        payload = _serializer().loads(token, max_age=current_app.config['TOKEN_MAX_AGE'])
    except SignatureExpired:
        raise AuthError(EXPIRED_TOKEN) from None
    except BadData:
        raise AuthError(INVALID_TOKEN) from None
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
        raise AuthError(INVALID_TOKEN)
    uid, sid = payload['uid'], payload['sid']
    if type(uid) is not int or uid < 1:
        raise AuthError(INVALID_TOKEN)
    if not isinstance(sid, str) or not NONCE_PATTERN.fullmatch(sid):
        raise AuthError(INVALID_TOKEN)
    return uid, sid


def authenticate(header_value):
    """Valida o cabeçalho Authorization e devolve o usuário ativo correspondente."""
    uid, sid = _load_payload(_extract_token(header_value))
    user = User.find_by_id(uid)
    if user is None or not user.auth_nonce or not hmac.compare_digest(user.auth_nonce, sid):
        raise AuthError(INVALID_TOKEN)
    if not user.active:
        raise ForbiddenError(INACTIVE_USER)
    return user


def optional_actor():
    """Sem cabeçalho: anônimo (None). Com cabeçalho, válido ou não: verificação completa."""
    header_value = request.headers.get('Authorization')
    if header_value is None:
        return None
    return authenticate(header_value)


def require_actor():
    header_value = request.headers.get('Authorization')
    if header_value is None:
        raise AuthError(MISSING_TOKEN, headers={'WWW-Authenticate': 'Bearer'})
    return authenticate(header_value)
