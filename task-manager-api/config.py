"""Configuração lida do ambiente, validada antes de qualquer acesso ao banco."""
import os

SECRET_KEY_MIN_LENGTH = 32
DEFAULT_DATABASE_URL = 'sqlite:///tasks.db'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000
DEFAULT_TOKEN_MAX_AGE = 3600
DEFAULT_CORS_ORIGINS = '*'
TRUE_VALUES = ('1', 'true', 'yes', 'on')


class ConfigError(Exception):
    pass


def _int(environ, name, default):
    raw = environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f'{name} deve ser um número inteiro') from None


def load_config(overrides=None, environ=None):
    environ = os.environ if environ is None else environ
    config = {
        'SECRET_KEY': environ.get('SECRET_KEY'),
        'SQLALCHEMY_DATABASE_URI': environ.get('DATABASE_URL') or DEFAULT_DATABASE_URL,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEBUG': environ.get('FLASK_DEBUG', '0').strip().lower() in TRUE_VALUES,
        'HOST': environ.get('HOST') or DEFAULT_HOST,
        'PORT': _int(environ, 'PORT', DEFAULT_PORT),
        'CORS_ORIGINS': environ.get('CORS_ORIGINS') or DEFAULT_CORS_ORIGINS,
        'TOKEN_MAX_AGE': _int(environ, 'TOKEN_MAX_AGE', DEFAULT_TOKEN_MAX_AGE),
    }
    config.update(overrides or {})
    # Sempre: parâmetros SQL fora de mensagens de erro e de logs (F-05).
    config['SQLALCHEMY_ECHO'] = False
    config['SQLALCHEMY_ENGINE_OPTIONS'] = {**config.get('SQLALCHEMY_ENGINE_OPTIONS', {}), 'hide_parameters': True}
    _validate(config)
    return config


def _validate(config):
    secret = config.get('SECRET_KEY')
    if not isinstance(secret, str) or len(secret) < SECRET_KEY_MIN_LENGTH:
        raise ConfigError(f'SECRET_KEY ausente ou com menos de {SECRET_KEY_MIN_LENGTH} caracteres')
    max_age = config.get('TOKEN_MAX_AGE')
    if type(max_age) is not int or max_age <= 0:
        raise ConfigError('TOKEN_MAX_AGE deve ser um inteiro positivo')
    port = config.get('PORT')
    if type(port) is not int or not 0 < port < 65536:
        raise ConfigError('PORT inválida')
