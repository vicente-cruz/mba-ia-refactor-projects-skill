# Faixas de desconto sobre o faturamento bruto: (limite exclusivo, percentual), da maior para a menor.
FAIXAS_DESCONTO = [
    (10000, 0.1),
    (5000, 0.05),
    (1000, 0.02),
]


def calcular_desconto(faturamento):
    for limite, percentual in FAIXAS_DESCONTO:
        if faturamento > limite:
            return faturamento * percentual
    return 0


def vendas(db):
    row = db.execute("""
        SELECT COUNT(*) AS total_pedidos,
               SUM(total) AS faturamento,
               COALESCE(SUM(status = 'pendente'), 0) AS pendentes,
               COALESCE(SUM(status = 'aprovado'), 0) AS aprovados,
               COALESCE(SUM(status = 'cancelado'), 0) AS cancelados
        FROM pedidos
    """).fetchone()

    total_pedidos = row["total_pedidos"]
    faturamento = row["faturamento"]
    if faturamento is None:
        faturamento = 0
    desconto = calcular_desconto(faturamento)

    return {
        "total_pedidos": total_pedidos,
        "faturamento_bruto": round(faturamento, 2),
        "desconto_aplicavel": round(desconto, 2),
        "faturamento_liquido": round(faturamento - desconto, 2),
        "pedidos_pendentes": row["pendentes"],
        "pedidos_aprovados": row["aprovados"],
        "pedidos_cancelados": row["cancelados"],
        "ticket_medio": round(faturamento / total_pedidos, 2) if total_pedidos > 0 else 0,
    }
