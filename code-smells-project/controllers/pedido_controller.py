import logging

from errors import NotFoundError, ValidationError
from models import pedido

logger = logging.getLogger(__name__)

# Casos de uso: recebem a conexão por parâmetro; a rota obtém a conexão da instância e a repassa.


def criar_pedido(db, dados):
    usuario_id, itens = pedido.validar_novo_pedido(dados)
    resultado = pedido.criar(db, usuario_id, itens)
    # Notificações continuam simuladas (sem integração real), agora como log.
    logger.info("Notificação simulada (e-mail, SMS, push): pedido %s criado para usuario %s",
                resultado["pedido_id"], usuario_id)
    return resultado


def listar_pedidos_usuario(db, usuario_id):
    return pedido.listar_por_usuario(db, usuario_id)


def listar_todos_pedidos(db):
    return pedido.listar_todos(db)


def atualizar_status_pedido(db, pedido_id, dados):
    if not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    novo_status = dados.get("status", "")
    if novo_status not in pedido.STATUS_VALIDOS:
        raise ValidationError("Status inválido")
    if not pedido.existe(db, pedido_id):
        raise NotFoundError("Pedido não encontrado")
    pedido.atualizar_status(db, pedido_id, novo_status)

    if novo_status == "aprovado":
        logger.info("Notificação: pedido %s foi aprovado; preparar envio.", pedido_id)
    if novo_status == "cancelado":
        logger.info("Notificação: pedido %s cancelado. Devolver estoque.", pedido_id)
