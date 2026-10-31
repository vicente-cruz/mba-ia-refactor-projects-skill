import logging
import os
import secrets

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"
AMBIENTE = "producao"

SEED_SENHA_VARS = {
    "admin@loja.com": "SEED_SENHA_ADMIN",
    "joao@email.com": "SEED_SENHA_JOAO",
    "maria@email.com": "SEED_SENHA_MARIA",
}


def _secret_key():
    value = os.environ.get("SECRET_KEY")
    if value:
        return value
    logger.warning("SECRET_KEY não definida; usando chave efêmera de desenvolvimento.")
    return secrets.token_hex(32)


def load_config():
    return {
        "SECRET_KEY": _secret_key(),
        "DATABASE_PATH": os.environ.get("DATABASE_PATH", "loja.db"),
        "DEBUG": os.environ.get("FLASK_DEBUG", "0") == "1",
        "HOST": os.environ.get("HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "ADMIN_TOKEN": os.environ.get("ADMIN_TOKEN") or None,
        "SEED_SENHAS": {email: os.environ.get(var, "") for email, var in SEED_SENHA_VARS.items()},
    }
