from errors import ValidationError

TABELAS = ("produtos", "usuarios", "pedidos", "itens_pedido")
ORDEM_RESET = ("itens_pedido", "pedidos", "produtos", "usuarios")
LIMITE_ESTOQUE_PADRAO = 5


def resetar(db):
    with db:
        for tabela in ORDEM_RESET:
            db.execute(f"DELETE FROM {tabela}")


def verificar_conexao(db):
    db.execute("SELECT 1")


def contagens(db):
    return {tabela: db.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] for tabela in TABELAS}


def _contagem_por_tabela(db, parametros):
    return [{"tabela": tabela, "quantidade": quantidade} for tabela, quantidade in contagens(db).items()]


def _pedidos_por_status(db, parametros):
    rows = db.execute(
        "SELECT status, COUNT(*) AS quantidade, SUM(total) AS total FROM pedidos GROUP BY status ORDER BY status"
    )
    return [dict(row) for row in rows]


def _produtos_estoque_baixo(db, parametros):
    limite = parametros.get("limite", LIMITE_ESTOQUE_PADRAO)
    if not isinstance(limite, int) or isinstance(limite, bool) or limite < 0:
        raise ValidationError("Parâmetro 'limite' deve ser inteiro maior ou igual a zero")
    rows = db.execute(
        "SELECT id, nome, estoque FROM produtos WHERE estoque <= ? ORDER BY id", (limite,)
    )
    return [dict(row) for row in rows]


def _usuarios_por_tipo(db, parametros):
    rows = db.execute("SELECT tipo, COUNT(*) AS quantidade FROM usuarios GROUP BY tipo ORDER BY tipo")
    return [dict(row) for row in rows]


# Catálogo fechado de consultas administrativas somente leitura; nenhuma seleciona a coluna senha.
CONSULTAS = {
    "contagem_por_tabela": (_contagem_por_tabela, ()),
    "pedidos_por_status": (_pedidos_por_status, ()),
    "produtos_estoque_baixo": (_produtos_estoque_baixo, ("limite",)),
    "usuarios_por_tipo": (_usuarios_por_tipo, ()),
}


def executar_consulta(db, nome, parametros):
    # O tipo é verificado antes da busca: lista/objeto JSON não são hasháveis.
    if not isinstance(nome, str) or nome not in CONSULTAS:
        raise ValidationError("Consulta inválida. Válidas: " + str(list(CONSULTAS)))
    funcao, aceitos = CONSULTAS[nome]
    if not isinstance(parametros, dict) or any(chave not in aceitos for chave in parametros):
        raise ValidationError("Parâmetros inválidos para a consulta " + nome)
    return funcao(db, parametros)
