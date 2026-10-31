import logging
import re

from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

TIPO_PADRAO = "cliente"

COLUNAS_PUBLICAS = "id, nome, email, tipo, criado_em"

# Formato gravado por generate_password_hash (Werkzeug 3): "scrypt:n:r:p$salt$hex" ou
# "pbkdf2:digest:iteracoes$salt$hex", com parâmetros inteiros positivos, salt alfanumérico e hash
# hexadecimal minúsculo. Tudo ASCII: conteúdo fora disso não chega ao check_password_hash.
FORMATO_HASH = re.compile(
    r"(?:scrypt:[1-9][0-9]*:[1-9][0-9]*:[1-9][0-9]*|pbkdf2:[a-z0-9_]+:[1-9][0-9]*)"
    r"\$[A-Za-z0-9]+\$[0-9a-f]+"
)


def to_public_dict(row):
    return {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "tipo": row["tipo"],
        "criado_em": row["criado_em"],
    }


def listar(db):
    return [to_public_dict(row) for row in db.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios")]


def buscar_por_id(db, usuario_id):
    row = db.execute(f"SELECT {COLUNAS_PUBLICAS} FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return to_public_dict(row) if row else None


def criar(db, nome, email, senha, tipo=TIPO_PADRAO):
    with db:
        cursor = db.execute(
            "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
            (nome, email, generate_password_hash(senha), tipo),
        )
    return cursor.lastrowid


def _recusar_formato():
    # Não registra o conteúdo armazenado.
    logger.warning("Senha armazenada em formato inválido ou não suportado; autenticação recusada.")
    return False


def _senha_confere(senha_armazenada, senha):
    """Verifica um hash do Werkzeug; formatos legados ou inválidos nunca autenticam (D-4 a)."""
    if not isinstance(senha_armazenada, str) or not FORMATO_HASH.fullmatch(senha_armazenada):
        return _recusar_formato()
    try:
        return check_password_hash(senha_armazenada, senha)
    except (ValueError, OverflowError):
        # Estrutura válida, mas parâmetros recusados pelo hashlib: digest não suportado
        # (UnsupportedDigestmodError é ValueError), n do scrypt que não é potência de 2,
        # iterações zero ou valores grandes demais para o C (OverflowError).
        return _recusar_formato()


def autenticar(db, email, senha):
    # O schema não impõe e-mail único: verifica cada cadastro com o e-mail, na ordem de criação.
    rows = db.execute(
        "SELECT id, nome, email, tipo, senha FROM usuarios WHERE email = ? ORDER BY id", (email,)
    ).fetchall()
    for row in rows:
        if _senha_confere(row["senha"], senha):
            return {"id": row["id"], "nome": row["nome"], "email": row["email"], "tipo": row["tipo"]}
    return None
