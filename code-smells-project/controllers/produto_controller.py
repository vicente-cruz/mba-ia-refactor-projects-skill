import logging
import math

from errors import NotFoundError, ValidationError
from models import produto

logger = logging.getLogger(__name__)


def listar_produtos(db):
    produtos = produto.listar(db)
    logger.info("Listando %s produtos", len(produtos))
    return produtos


def buscar_produto(db, produto_id):
    encontrado = produto.buscar_por_id(db, produto_id)
    if not encontrado:
        raise NotFoundError("Produto não encontrado", extra={"sucesso": False})
    return encontrado


def criar_produto(db, dados):
    novo = produto.validar(dados)
    produto_id = produto.criar(db, novo)
    logger.info("Produto criado com ID: %s", produto_id)
    return produto_id


def atualizar_produto(db, produto_id, dados):
    if not produto.buscar_por_id(db, produto_id):
        raise NotFoundError("Produto não encontrado")
    produto.atualizar(db, produto_id, produto.validar(dados))


def deletar_produto(db, produto_id):
    if not produto.buscar_por_id(db, produto_id):
        raise NotFoundError("Produto não encontrado")
    produto.deletar(db, produto_id)
    logger.info("Produto %s deletado", produto_id)


def _preco_opcional(nome_parametro, valor):
    if not valor:
        return None
    try:
        numero = float(valor)
    except ValueError:
        numero = None
    if numero is None or not math.isfinite(numero):
        raise ValidationError(f"Parâmetro {nome_parametro} inválido")
    return numero


def buscar_produtos(db, termo, categoria, preco_min, preco_max):
    return produto.buscar(
        db,
        termo,
        categoria,
        _preco_opcional("preco_min", preco_min),
        _preco_opcional("preco_max", preco_max),
    )
