"""Casos de uso de usuários e login, com a matriz de permissões de D-1(a)."""
import logging

from auth import issue_token, PERMISSION_DENIED, MISSING_TOKEN
from controllers.validation import require_non_empty_object
from database import db, commit_or_rollback
from errors import AuthError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from models.clock import utc_now
from models.task import Task
from models.user import DEFAULT_ROLE, PASSWORD_MIN_LENGTH, VALID_ROLES, User

logger = logging.getLogger('task_manager')

USER_NOT_FOUND = 'Usuário não encontrado'
EMAIL_TAKEN = 'Email já cadastrado'
INVALID_CREDENTIALS = 'Credenciais inválidas'


def _get_or_404(user_id):
    user = User.find_by_id(user_id)
    if user is None:
        raise NotFoundError(USER_NOT_FOUND)
    return user


def _required_text(data, field, missing_message, invalid_message):
    value = data.get(field)
    if not value:
        raise ValidationError(missing_message)
    if not isinstance(value, str):
        raise ValidationError(invalid_message)
    return value


# ------------------------------------------------------------------ leitura
def list_users():
    return [user.to_summary_dict(task_count) for user, task_count in User.list_with_task_counts()]


def get_user(user_id):
    user = _get_or_404(user_id)
    data = user.to_dict()
    data['tasks'] = [task.to_dict() for task in Task.for_user(user_id)]
    return data


def get_user_tasks(user_id):
    _get_or_404(user_id)
    now = utc_now()
    return [task.to_user_task_dict(now) for task in Task.for_user(user_id)]


# ------------------------------------------------------------------ escrita
def create_user(data, actor):
    data = require_non_empty_object(data)
    name = _required_text(data, 'name', 'Nome é obrigatório', 'Nome inválido')
    email = _required_text(data, 'email', 'Email é obrigatório', 'Email inválido')
    password = _required_text(data, 'password', 'Senha é obrigatória', 'Senha inválida')
    if not User.is_valid_email(email):
        raise ValidationError('Email inválido')
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError('Senha deve ter no mínimo 4 caracteres')
    if User.email_taken(email):
        raise ConflictError(EMAIL_TAKEN)
    role = data.get('role', DEFAULT_ROLE)
    if role not in VALID_ROLES:
        raise ValidationError('Role inválido')
    if role != DEFAULT_ROLE:
        if actor is None:
            raise AuthError(MISSING_TOKEN, headers={'WWW-Authenticate': 'Bearer'})
        if not actor.is_admin():
            raise ForbiddenError(PERMISSION_DENIED)
    user = User(name=name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    commit_or_rollback('Erro ao criar usuário')
    logger.info('Usuário criado: id=%s', user.id)
    return user.to_dict()


def _authorize_update(actor, target, data):
    if actor.is_admin():
        return
    if actor.id != target.id:
        raise ForbiddenError(PERMISSION_DENIED)
    if 'role' in data and data['role'] != target.role:
        raise ForbiddenError(PERMISSION_DENIED)
    if 'active' in data and data['active'] != target.active:
        raise ForbiddenError(PERMISSION_DENIED)


def _validated_update(user_id, data):
    changes = {}
    if 'name' in data:
        if not isinstance(data['name'], str) or not data['name']:
            raise ValidationError('Nome inválido')
        changes['name'] = data['name']
    if 'email' in data:
        if not User.is_valid_email(data['email']):
            raise ValidationError('Email inválido')
        if User.email_taken(data['email'], except_user_id=user_id):
            raise ConflictError(EMAIL_TAKEN)
        changes['email'] = data['email']
    if 'password' in data:
        if not isinstance(data['password'], str):
            raise ValidationError('Senha inválida')
        if len(data['password']) < PASSWORD_MIN_LENGTH:
            raise ValidationError('Senha muito curta')
        changes['password'] = data['password']
    if 'role' in data:
        if data['role'] not in VALID_ROLES:
            raise ValidationError('Role inválido')
        changes['role'] = data['role']
    if 'active' in data:
        if not isinstance(data['active'], bool):
            raise ValidationError('Campo active inválido')
        changes['active'] = data['active']
    return changes


def update_user(user_id, load_body, actor):
    target = _get_or_404(user_id)
    data = require_non_empty_object(load_body())
    _authorize_update(actor, target, data)
    changes = _validated_update(user_id, data)
    for field in ('name', 'email', 'role', 'active'):
        if field in changes:
            setattr(target, field, changes[field])
    if 'password' in changes:
        target.change_password(changes['password'])
    commit_or_rollback('Erro ao atualizar')
    logger.info('Usuário atualizado: id=%s', user_id)
    return target.to_dict()


def delete_user(user_id, actor):
    target = _get_or_404(user_id)
    if not actor.is_admin():
        raise ForbiddenError(PERMISSION_DENIED)
    for task in Task.for_user(user_id):
        db.session.delete(task)
    db.session.delete(target)
    commit_or_rollback('Erro ao deletar')
    logger.info('Usuário deletado: id=%s', user_id)
    return {'message': 'Usuário deletado com sucesso'}


def login(data):
    data = require_non_empty_object(data)
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        raise ValidationError('Email e senha são obrigatórios')
    if not isinstance(email, str) or not isinstance(password, str):
        raise AuthError(INVALID_CREDENTIALS)
    user = User.find_by_email(email)
    if user is None:
        raise AuthError(INVALID_CREDENTIALS)
    valid, needs_rehash = user.verify_password(password)
    if not valid:
        raise AuthError(INVALID_CREDENTIALS)
    if not user.active:
        raise ForbiddenError('Usuário inativo')
    changed = user.ensure_auth_nonce()
    if needs_rehash:
        user.set_password(password)  # migração do MD5 legado; não troca o auth_nonce
        changed = True
    if changed:
        commit_or_rollback('Erro interno')
    return {
        'message': 'Login realizado com sucesso',
        'user': user.to_dict(),
        'token': issue_token(user),
    }
