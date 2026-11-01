"""Casos de uso de categorias."""
import logging

from controllers.validation import optional_text, require_non_empty_object, require_object
from database import db, commit_or_rollback
from errors import NotFoundError, ValidationError
from models.category import DEFAULT_COLOR, Category

logger = logging.getLogger('task_manager')

CATEGORY_NOT_FOUND = 'Categoria não encontrada'


def _validate_color(value):
    if not Category.is_valid_color(value):
        raise ValidationError('Cor inválida')
    return value


def _get_or_404(category_id):
    category = Category.find_by_id(category_id)
    if category is None:
        raise NotFoundError(CATEGORY_NOT_FOUND)
    return category


def list_categories():
    result = []
    for category, task_count in Category.list_with_task_counts():
        data = category.to_dict()
        data['task_count'] = task_count
        result.append(data)
    return result


def create_category(data):
    data = require_non_empty_object(data)
    name = data.get('name')
    if not name:
        raise ValidationError('Nome é obrigatório')
    if not isinstance(name, str):
        raise ValidationError('Nome inválido')
    category = Category(
        name=name,
        description=optional_text(data.get('description', ''), 'Descrição inválida'),
        color=_validate_color(data.get('color', DEFAULT_COLOR)),
    )
    db.session.add(category)
    commit_or_rollback('Erro ao criar categoria')
    logger.info('Categoria criada: id=%s', category.id)
    return category.to_dict()


def update_category(category_id, load_body):
    category = _get_or_404(category_id)
    data = require_object(load_body())
    changes = {}
    if 'name' in data:
        if data['name'] is None:
            raise ValidationError('Nome é obrigatório')
        if not isinstance(data['name'], str) or not data['name']:
            raise ValidationError('Nome inválido')
        changes['name'] = data['name']
    if 'description' in data:
        changes['description'] = optional_text(data['description'], 'Descrição inválida')
    if 'color' in data:
        changes['color'] = _validate_color(data['color'])
    for field, value in changes.items():
        setattr(category, field, value)
    commit_or_rollback('Erro ao atualizar')
    return category.to_dict()


def delete_category(category_id):
    category = _get_or_404(category_id)
    db.session.delete(category)
    commit_or_rollback('Erro ao deletar')
    logger.info('Categoria deletada: id=%s', category_id)
    return {'message': 'Categoria deletada'}
