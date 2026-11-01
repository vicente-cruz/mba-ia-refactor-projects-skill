"""Validações de entrada compartilhadas pelos controllers (funções puras)."""
import math

from errors import ValidationError, INVALID_BODY_MESSAGE


def require_non_empty_object(data):
    """POST e PUT de tasks/users e login: corpo falso ou não-objeto → 400."""
    if not data or not isinstance(data, dict):
        raise ValidationError(INVALID_BODY_MESSAGE)
    return data


def require_object(data):
    """PUT /categories: {} é aceito (sem alteração); não-objeto → 400."""
    if not isinstance(data, dict):
        raise ValidationError(INVALID_BODY_MESSAGE)
    return data


def is_strict_int(value):
    return type(value) is int


def parse_reference_id(value, message):
    """IDs de referência no corpo: None ou inteiro >= 1 (bool, str, float e zero são inválidos)."""
    if value is None:
        return None
    if is_strict_int(value) and value >= 1:
        return value
    raise ValidationError(message)


def parse_integral_number(value):
    """int, ou float finito com valor inteiro (2.0 → 2). Retorna None se inválido."""
    if isinstance(value, bool):
        return None
    if is_strict_int(value):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def optional_text(value, message):
    """Texto opcional: str ou None."""
    if value is not None and not isinstance(value, str):
        raise ValidationError(message)
    return value
