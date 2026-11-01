"""Fonte única de "agora" em UTC ingênuo (compatível com os valores já gravados)."""
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
