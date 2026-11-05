import logging
import sqlite3

from config import AMBIENTE, API_VERSION
from errors import ValidationError
from models import admin

logger = logging.getLogger(__name__)


def indice():
    return {
        "mensagem": "Bem-vindo à API da Loja",
        "versao": API_VERSION,
        "endpoints": {
            "produtos": "/produtos",
            "usuarios": "/usuarios",
            "pedidos": "/pedidos",
            "login": "/login",
            "relatorios": "/relatorios/vendas",
            "health": "/health",
        },
    }


def health_check(obter_db, debug):
    """Retorna (dados, saudavel). `obter_db` é chamado aqui para que falhas ao abrir o banco
    também resultem em status de erro, como antes."""
    try:
        db = obter_db()
        admin.verificar_conexao(db)
        contagens = admin.contagens(db)
    except sqlite3.Error:
        logger.exception("Health check falhou")
        return {"status": "erro", "detalhes": "Banco de dados indisponível"}, False
    return {
        "status": "ok",
        "database": "connected",
        "counts": {
            "produtos": contagens["produtos"],
            "usuarios": contagens["usuarios"],
            "pedidos": contagens["pedidos"],
        },
        "versao": API_VERSION,
        "ambiente": AMBIENTE,
        "debug": debug,
    }, True


def resetar_banco(db):
    admin.resetar(db)
    logger.warning("Banco de dados resetado via /admin/reset-db")


def executar_consulta(db, dados):
    if not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    if "sql" in dados:
        raise ValidationError("Execução de SQL arbitrário não é suportada; informe 'consulta'")
    nome = dados.get("consulta")
    if not nome:
        raise ValidationError("Consulta não informada")
    return admin.executar_consulta(db, nome, dados.get("parametros", {}))
