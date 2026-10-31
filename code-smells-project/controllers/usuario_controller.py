import logging

from database import get_db
from errors import DomainError, NotFoundError, ValidationError
from models import usuario

logger = logging.getLogger(__name__)


def _texto_preenchido(valor):
    return isinstance(valor, str) and valor != ""


def listar_usuarios():
    return usuario.listar(get_db())


def buscar_usuario(usuario_id):
    encontrado = usuario.buscar_por_id(get_db(), usuario_id)
    if not encontrado:
        raise NotFoundError("Usuário não encontrado")
    return encontrado


def criar_usuario(dados):
    if not dados or not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    nome = dados.get("nome", "")
    email = dados.get("email", "")
    senha = dados.get("senha", "")
    if not all(_texto_preenchido(valor) for valor in (nome, email, senha)):
        raise ValidationError("Nome, email e senha são obrigatórios")
    usuario_id = usuario.criar(get_db(), nome, email, senha)
    logger.info("Usuário criado: id=%s", usuario_id)
    return usuario_id


def login(dados):
    if not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    email = dados.get("email", "")
    senha = dados.get("senha", "")
    if not _texto_preenchido(email) or not _texto_preenchido(senha):
        raise ValidationError("Email e senha são obrigatórios")
    autenticado = usuario.autenticar(get_db(), email, senha)
    if not autenticado:
        logger.info("Login falhou")
        raise DomainError("Email ou senha inválidos", 401, extra={"sucesso": False})
    logger.info("Login bem-sucedido: usuário id=%s", autenticado["id"])
    return autenticado
