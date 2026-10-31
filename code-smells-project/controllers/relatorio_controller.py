from database import get_db
from models import relatorio


def relatorio_vendas():
    return relatorio.vendas(get_db())
