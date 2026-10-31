from errors import ValidationError

STATUS_VALIDOS = ["pendente", "aprovado", "enviado", "entregue", "cancelado"]
STATUS_INICIAL = "pendente"
PRODUTO_DESCONHECIDO = "Desconhecido"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validar_novo_pedido(dados):
    if not dados or not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")

    usuario_id = dados.get("usuario_id")
    itens = dados.get("itens", [])

    if not usuario_id:
        raise ValidationError("Usuario ID é obrigatório")
    if not _is_int(usuario_id):
        raise ValidationError("Usuario ID inválido")
    if not itens:
        raise ValidationError("Pedido deve ter pelo menos 1 item")
    if not isinstance(itens, list):
        raise ValidationError("Itens inválidos")
    for item in itens:
        if (not isinstance(item, dict) or not _is_int(item.get("produto_id"))
                or not _is_int(item.get("quantidade")) or item["quantidade"] <= 0):
            raise ValidationError("Item inválido: produto_id e quantidade devem ser inteiros e quantidade maior que zero")

    return usuario_id, [{"produto_id": i["produto_id"], "quantidade": i["quantidade"]} for i in itens]


def _erro_pedido(mensagem):
    return ValidationError(mensagem, extra={"sucesso": False})


def criar(db, usuario_id, itens):
    # Toda a operação (pedido, itens e baixa de estoque) é confirmada ou desfeita junta.
    with db:
        total = 0
        produtos = {}
        for item in itens:
            produto = db.execute(
                "SELECT id, nome, preco, estoque FROM produtos WHERE id = ?", (item["produto_id"],)
            ).fetchone()
            if produto is None:
                raise _erro_pedido("Produto " + str(item["produto_id"]) + " não encontrado")
            if produto["estoque"] < item["quantidade"]:
                raise _erro_pedido("Estoque insuficiente para " + produto["nome"])
            produtos[item["produto_id"]] = produto
            total = total + (produto["preco"] * item["quantidade"])

        cursor = db.execute(
            "INSERT INTO pedidos (usuario_id, status, total) VALUES (?, ?, ?)",
            (usuario_id, STATUS_INICIAL, total),
        )
        pedido_id = cursor.lastrowid

        for item in itens:
            produto = produtos[item["produto_id"]]
            db.execute(
                "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)",
                (pedido_id, item["produto_id"], item["quantidade"], produto["preco"]),
            )
            baixa = db.execute(
                "UPDATE produtos SET estoque = estoque - ? WHERE id = ? AND estoque >= ?",
                (item["quantidade"], item["produto_id"], item["quantidade"]),
            )
            if baixa.rowcount == 0:
                raise _erro_pedido("Estoque insuficiente para " + produto["nome"])

    return {"pedido_id": pedido_id, "total": total}


def _listar(db, usuario_id=None):
    query = """
        SELECT p.id, p.usuario_id, p.status, p.total, p.criado_em,
               i.id AS item_id, i.produto_id, i.quantidade, i.preco_unitario,
               pr.id AS produto_encontrado, pr.nome AS produto_nome
        FROM pedidos p
        LEFT JOIN itens_pedido i ON i.pedido_id = p.id
        LEFT JOIN produtos pr ON pr.id = i.produto_id
    """
    params = ()
    if usuario_id is not None:
        query += " WHERE p.usuario_id = ?"
        params = (usuario_id,)
    query += " ORDER BY p.id, i.id"

    pedidos = {}
    for row in db.execute(query, params):
        pedido = pedidos.setdefault(row["id"], {
            "id": row["id"],
            "usuario_id": row["usuario_id"],
            "status": row["status"],
            "total": row["total"],
            "criado_em": row["criado_em"],
            "itens": [],
        })
        if row["item_id"] is not None:
            pedido["itens"].append({
                "produto_id": row["produto_id"],
                "produto_nome": row["produto_nome"] if row["produto_encontrado"] is not None else PRODUTO_DESCONHECIDO,
                "quantidade": row["quantidade"],
                "preco_unitario": row["preco_unitario"],
            })
    return list(pedidos.values())


def listar_todos(db):
    return _listar(db)


def listar_por_usuario(db, usuario_id):
    return _listar(db, usuario_id)


def existe(db, pedido_id):
    return db.execute("SELECT 1 FROM pedidos WHERE id = ?", (pedido_id,)).fetchone() is not None


def atualizar_status(db, pedido_id, novo_status):
    with db:
        db.execute("UPDATE pedidos SET status = ? WHERE id = ?", (novo_status, pedido_id))
