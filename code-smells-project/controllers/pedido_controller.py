import logging

from database import get_db
from errors import NotFoundError, ValidationError
from models import pedido

logger = logging.getLogger(__name__)


def criar_pedido(dados):
    usuario_id, itens = pedido.validar_novo_pedido(dados)
    resultado = pedido.criar(get_db(), usuario_id, itens)
    # Notificações continuam simuladas (sem integração real), agora como log.
    logger.info("Notificação simulada (e-mail, SMS, push): pedido %s criado para usuario %s",
                resultado["pedido_id"], usuario_id)
    return resultado


def listar_pedidos_usuario(usuario_id):
    return pedido.listar_por_usuario(get_db(), usuario_id)


def listar_todos_pedidos():
    return pedido.listar_todos(get_db())


def atualizar_status_pedido(pedido_id, dados):
    if not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    novo_status = dados.get("status", "")
    if novo_status not in pedido.STATUS_VALIDOS:
        raise ValidationError("Status inválido")
    db = get_db()
    if not pedido.existe(db, pedido_id):
        raise NotFoundError("Pedido não encontrado")
    pedido.atualizar_status(db, pedido_id, novo_status)

    if novo_status == "aprovado":
        logger.info("Notificação: pedido %s foi aprovado; preparar envio.", pedido_id)
    if novo_status == "cancelado":
        logger.info("Notificação: pedido %s cancelado. Devolver estoque.", pedido_id)
