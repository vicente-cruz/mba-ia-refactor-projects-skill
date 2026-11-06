import logging
import os
import secrets

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"

SEED_SENHA_VARS = {
    "admin@loja.com": "SEED_SENHA_ADMIN",
    "joao@email.com": "SEED_SENHA_JOAO",
    "maria@email.com": "SEED_SENHA_MARIA",
}

# SEED_ON_STARTUP: ausente = ligado (comportamento histórico); "1" = ligado; "0" = desligado.
# Qualquer outro texto (inclusive vazio, "true", "2") é recusado: os dois valores aceitos são textos
# não vazios, então uma conversão por valor de verdade ligaria o seed com "0".
SEED_ON_STARTUP_VALORES = {"1": True, "0": False}


class ConfigError(Exception):
    """Configuração inválida; levantada antes de qualquer acesso ao banco."""


def _secret_key():
    value = os.environ.get("SECRET_KEY")
    if value:
        return value
    logger.warning("SECRET_KEY não definida; usando chave efêmera de desenvolvimento.")
    return secrets.token_hex(32)


def _seed_on_startup():
    valor = os.environ.get("SEED_ON_STARTUP")
    if valor is None:
        return True
    if valor not in SEED_ON_STARTUP_VALORES:
        raise ConfigError(
            f"SEED_ON_STARTUP inválido ({valor!r}): use '1' (ligado) ou '0' (desligado); ausente = ligado"
        )
    return SEED_ON_STARTUP_VALORES[valor]


def load_config():
    return {
        "SECRET_KEY": _secret_key(),
        "DATABASE_PATH": os.environ.get("DATABASE_PATH", "loja.db"),
        "DEBUG": os.environ.get("FLASK_DEBUG", "0") == "1",
        "HOST": os.environ.get("HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "ADMIN_TOKEN": os.environ.get("ADMIN_TOKEN") or None,
        "SEED_ON_STARTUP": _seed_on_startup(),
        "SEED_SENHAS": {email: os.environ.get(var, "") for email, var in SEED_SENHA_VARS.items()},
    }


def validate_config(config):
    """Valida a configuração final (ambiente + overrides da factory) antes de abrir o banco."""
    if not isinstance(config.get("SEED_ON_STARTUP"), bool):
        raise ConfigError("SEED_ON_STARTUP deve ser bool nos overrides de create_app (True ou False)")
