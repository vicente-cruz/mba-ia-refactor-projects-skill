import math

from errors import ValidationError

CATEGORIAS_VALIDAS = ["informatica", "moveis", "vestuario", "geral", "eletronicos", "livros"]
CATEGORIA_PADRAO = "geral"
NOME_MIN_LENGTH = 2
NOME_MAX_LENGTH = 200
CAMPOS_OBRIGATORIOS = (
    ("nome", "Nome é obrigatório"),
    ("preco", "Preço é obrigatório"),
    ("estoque", "Estoque é obrigatório"),
)

COLUNAS = "id, nome, descricao, preco, estoque, categoria, ativo, criado_em"


def _is_number(value):
    # JSON aceita 1e309 (vira infinito) e as extensões NaN/Infinity; nenhum deles é valor válido.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validar(dados):
    if not dados or not isinstance(dados, dict):
        raise ValidationError("Dados inválidos")
    for campo, mensagem in CAMPOS_OBRIGATORIOS:
        if campo not in dados:
            raise ValidationError(mensagem)

    nome = dados["nome"]
    descricao = dados.get("descricao", "")
    preco = dados["preco"]
    estoque = dados["estoque"]
    categoria = dados.get("categoria", CATEGORIA_PADRAO)

    if not isinstance(nome, str):
        raise ValidationError("Nome inválido")
    if not isinstance(descricao, str):
        raise ValidationError("Descrição inválida")
    if not _is_number(preco):
        raise ValidationError("Preço inválido")
    if not _is_number(estoque):
        raise ValidationError("Estoque inválido")
    if preco < 0:
        raise ValidationError("Preço não pode ser negativo")
    if estoque < 0:
        raise ValidationError("Estoque não pode ser negativo")
    if len(nome) < NOME_MIN_LENGTH:
        raise ValidationError("Nome muito curto")
    if len(nome) > NOME_MAX_LENGTH:
        raise ValidationError("Nome muito longo")
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValidationError("Categoria inválida. Válidas: " + str(CATEGORIAS_VALIDAS))

    return {"nome": nome, "descricao": descricao, "preco": preco, "estoque": estoque, "categoria": categoria}


def to_dict(row):
    return {
        "id": row["id"],
        "nome": row["nome"],
        "descricao": row["descricao"],
        "preco": row["preco"],
        "estoque": row["estoque"],
        "categoria": row["categoria"],
        "ativo": row["ativo"],
        "criado_em": row["criado_em"],
    }


def listar(db):
    return [to_dict(row) for row in db.execute(f"SELECT {COLUNAS} FROM produtos")]


def buscar_por_id(db, produto_id):
    row = db.execute(f"SELECT {COLUNAS} FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    return to_dict(row) if row else None


def criar(db, produto):
    with db:
        cursor = db.execute(
            "INSERT INTO produtos (nome, descricao, preco, estoque, categoria) VALUES (?, ?, ?, ?, ?)",
            (produto["nome"], produto["descricao"], produto["preco"], produto["estoque"], produto["categoria"]),
        )
    return cursor.lastrowid


def atualizar(db, produto_id, produto):
    with db:
        db.execute(
            "UPDATE produtos SET nome = ?, descricao = ?, preco = ?, estoque = ?, categoria = ? WHERE id = ?",
            (produto["nome"], produto["descricao"], produto["preco"], produto["estoque"],
             produto["categoria"], produto_id),
        )


def deletar(db, produto_id):
    with db:
        db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))


def buscar(db, termo, categoria=None, preco_min=None, preco_max=None):
    query = f"SELECT {COLUNAS} FROM produtos WHERE 1=1"
    params = []
    if termo:
        query += " AND (nome LIKE ? OR descricao LIKE ?)"
        params += [f"%{termo}%", f"%{termo}%"]
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if preco_min:
        query += " AND preco >= ?"
        params.append(preco_min)
    if preco_max:
        query += " AND preco <= ?"
        params.append(preco_max)
    return [to_dict(row) for row in db.execute(query, params)]
