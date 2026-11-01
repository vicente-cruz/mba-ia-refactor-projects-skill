"""Casos de uso de tasks. Toda a entrada é validada antes de alterar a sessão."""
import logging
from datetime import datetime

from controllers.validation import (optional_text, parse_integral_number, parse_reference_id,
                                    require_non_empty_object)
from database import db, commit_or_rollback
from errors import NotFoundError, ValidationError
from models.category import Category
from models.clock import utc_now
from models.task import (DEFAULT_PRIORITY, DEFAULT_STATUS, DONE_STATUS, DUE_DATE_FORMAT,
                         MAX_PRIORITY, MIN_PRIORITY, TAG_SEPARATOR, TITLE_MAX_LENGTH, TITLE_MIN_LENGTH,
                         VALID_STATUSES, Task)
from models.user import User

logger = logging.getLogger('task_manager')

TASK_NOT_FOUND = 'Task não encontrada'
USER_NOT_FOUND = 'Usuário não encontrado'
CATEGORY_NOT_FOUND = 'Categoria não encontrada'
DATE_MESSAGE_CREATE = 'Formato de data inválido. Use YYYY-MM-DD'
DATE_MESSAGE_UPDATE = 'Formato de data inválido'
_ABSENT = object()


# ------------------------------------------------------------------ validação de campos
def _validate_title_length(title):
    if len(title) < TITLE_MIN_LENGTH:
        raise ValidationError('Título muito curto')
    if len(title) > TITLE_MAX_LENGTH:
        raise ValidationError('Título muito longo')
    return title


def _validate_status(status):
    if status not in VALID_STATUSES:
        raise ValidationError('Status inválido')
    return status


def _validate_priority(value):
    priority = parse_integral_number(value)
    if priority is None:
        raise ValidationError('Prioridade inválida')
    if priority < MIN_PRIORITY or priority > MAX_PRIORITY:
        raise ValidationError('Prioridade deve ser entre 1 e 5')
    return priority


def _resolve_user(value):
    user_id = parse_reference_id(value, 'Usuário inválido')
    if user_id is not None and User.find_by_id(user_id) is None:
        raise NotFoundError(USER_NOT_FOUND)
    return user_id


def _resolve_category(value):
    category_id = parse_reference_id(value, 'Categoria inválida')
    if category_id is not None and Category.find_by_id(category_id) is None:
        raise NotFoundError(CATEGORY_NOT_FOUND)
    return category_id


def _parse_due_date(value, message):
    if not value:
        return None
    if not isinstance(value, str):
        raise ValidationError(message)
    try:
        return datetime.strptime(value, DUE_DATE_FORMAT)
    except ValueError:
        raise ValidationError(message) from None


def _parse_tags(value):
    """POST: valor falso de qualquer tipo = sem tags (como o original)."""
    if not value:
        return None
    return _parse_tags_value(value)


def _parse_tags_update(value):
    """PUT: só null, "" e [] limpam as tags; 0, false, 0.0, {} etc. são inválidos."""
    if value is None or value == '' or value == []:
        return None
    return _parse_tags_value(value)


def _parse_tags_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(tag, str) and TAG_SEPARATOR not in tag for tag in value):
        return TAG_SEPARATOR.join(value)
    raise ValidationError('Tags inválidas')


def _validated_create(data):
    title = data.get('title')
    if not title:
        raise ValidationError('Título é obrigatório')
    if not isinstance(title, str):
        raise ValidationError('Título inválido')
    return {
        'title': _validate_title_length(title),
        'description': optional_text(data.get('description', ''), 'Descrição inválida'),
        'status': _validate_status(data.get('status', DEFAULT_STATUS)),
        'priority': _validate_priority(data.get('priority', DEFAULT_PRIORITY)),
        'user_id': _resolve_user(data.get('user_id')),
        'category_id': _resolve_category(data.get('category_id')),
        'due_date': _parse_due_date(data.get('due_date'), DATE_MESSAGE_CREATE),
        'tags': _parse_tags(data.get('tags')),
    }


def _validated_update(data):
    changes = {}
    if 'title' in data:
        if not isinstance(data['title'], str):
            raise ValidationError('Título inválido')
        changes['title'] = _validate_title_length(data['title'])
    if 'description' in data:
        changes['description'] = optional_text(data['description'], 'Descrição inválida')
    if 'status' in data:
        changes['status'] = _validate_status(data['status'])
    if 'priority' in data:
        changes['priority'] = _validate_priority(data['priority'])
    if 'user_id' in data:
        changes['user_id'] = _resolve_user(data['user_id'])
    if 'category_id' in data:
        changes['category_id'] = _resolve_category(data['category_id'])
    if 'due_date' in data:
        changes['due_date'] = _parse_due_date(data['due_date'], DATE_MESSAGE_UPDATE)
    if 'tags' in data:
        changes['tags'] = _parse_tags_update(data['tags'])
    return changes


def _get_or_404(task_id):
    task = Task.find_by_id(task_id)
    if task is None:
        raise NotFoundError(TASK_NOT_FOUND)
    return task


# ------------------------------------------------------------------ casos de uso
def list_tasks():
    now = utc_now()
    result = []
    for task, user_name, category_name in Task.list_with_relation_names():
        data = task.to_dict_with_overdue(now)
        data['user_name'] = user_name
        data['category_name'] = category_name
        result.append(data)
    return result


def get_task(task_id):
    return _get_or_404(task_id).to_dict_with_overdue()


def create_task(data):
    values = _validated_create(require_non_empty_object(data))
    task = Task(**values)
    db.session.add(task)
    commit_or_rollback('Erro ao criar task')
    logger.info('Task criada: id=%s', task.id)
    return task.to_dict()


def update_task(task_id, load_body):
    task = _get_or_404(task_id)
    changes = _validated_update(require_non_empty_object(load_body()))
    for field, value in changes.items():
        setattr(task, field, value)
    task.updated_at = utc_now()
    commit_or_rollback('Erro ao atualizar')
    logger.info('Task atualizada: id=%s', task.id)
    return task.to_dict()


def delete_task(task_id):
    task = _get_or_404(task_id)
    db.session.delete(task)
    commit_or_rollback('Erro ao deletar')
    logger.info('Task deletada: id=%s', task_id)
    return {'message': 'Task deletada com sucesso'}


def _parse_int_filter(raw, message):
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValidationError(message) from None


def search_tasks(text, status, priority, user_id):
    tasks = Task.search(
        text=text or None,
        status=status or None,
        priority=_parse_int_filter(priority, 'Prioridade inválida'),
        user_id=_parse_int_filter(user_id, 'Usuário inválido'),
    )
    return [task.to_dict() for task in tasks]


def task_stats():
    total = Task.count_all()
    by_status = Task.count_by_status()
    now = utc_now()
    overdue = sum(1 for task in Task.all_ordered() if task.is_overdue(now))
    done = by_status[DONE_STATUS]
    return {
        'total': total,
        'pending': by_status['pending'],
        'in_progress': by_status['in_progress'],
        'done': done,
        'cancelled': by_status['cancelled'],
        'overdue': overdue,
        'completion_rate': completion_rate(done, total),
    }


def completion_rate(done, total):
    return round((done / total) * 100, 2) if total > 0 else 0
