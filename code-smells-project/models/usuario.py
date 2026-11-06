import hashlib
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


# Hash preservável na migração: o mesmo formato aceito no login (FORMATO_HASH, com salt de qualquer
# tamanho), mais as condições estruturais do Werkzeug/hashlib: parâmetros numéricos que cabem num long
# de 64 bits; scrypt com n potência de 2 e hash de 64 bytes; pbkdf2 com digest conhecido pelo hashlib
# e hash do tamanho desse digest.
HASH_SCRYPT = re.compile(r"scrypt:([1-9][0-9]*):([1-9][0-9]*):([1-9][0-9]*)\$[A-Za-z0-9]+\$([0-9a-f]+)")
HASH_PBKDF2 = re.compile(r"pbkdf2:([a-z0-9_]+):([1-9][0-9]*)\$[A-Za-z0-9]+\$([0-9a-f]+)")
TAMANHO_HEX_SCRYPT = 128  # generate_password_hash usa scrypt com dklen=64
# Os parâmetros numéricos vão para inteiros C (long) no hashlib: acima de 2**63 - 1 (19 dígitos) o
# login recusa (OverflowError). Só números com até 19 dígitos chegam a int(), longe do limite de
# 4300 dígitos do Python.
MAX_DIGITOS = 19


def _inteiro_c(digitos):
    """Valor do parâmetro se couber num long de 64 bits; None caso contrário (sem converter textos longos)."""
    if len(digitos) > MAX_DIGITOS:
        return None
    valor = int(digitos)
    return valor if valor < 2 ** 63 else None


def _tamanho_digest(nome):
    """Tamanho (bytes) do digest; instancia o algoritmo sem processar dados nem executar o KDF."""
    try:
        return hashlib.new(nome).digest_size
    except (ValueError, TypeError):
        return None


def hash_preservavel(valor):
    """True quando o valor armazenado é um hash completo do Werkzeug (formato, parâmetros e tamanho).

    Qualquer outro valor não nulo (texto puro, formato inválido, BLOB, número) é credencial legada e
    deve ser invalidado por migrar_senhas.py. NULL não é credencial: a conta já não autentica.
    Não executa o KDF, não verifica senha e não converte números longos: sem exceções para texto
    arbitrário.
    """
    if not isinstance(valor, str):
        return False
    scrypt = HASH_SCRYPT.fullmatch(valor)
    if scrypt:
        n, r, p = (_inteiro_c(d) for d in scrypt.groups()[:3])
        if None in (n, r, p) or len(scrypt.group(4)) != TAMANHO_HEX_SCRYPT:
            return False
        return n > 1 and n & (n - 1) == 0
    pbkdf2 = HASH_PBKDF2.fullmatch(valor)
    if pbkdf2:
        nome, iteracoes, hexa = pbkdf2.groups()
        if _inteiro_c(iteracoes) is None:
            return False
        tamanho = _tamanho_digest(nome)
        return bool(tamanho) and len(hexa) == 2 * tamanho
    return False


def ids_com_credencial_legada(db):
    """IDs de usuários cuja coluna senha não é NULL nem um hash preservável. Não altera o banco."""
    tabela = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'usuarios'").fetchone()
    if tabela is None:
        return []
    rows = db.execute("SELECT id, senha FROM usuarios WHERE senha IS NOT NULL ORDER BY id")
    return [row[0] for row in rows if not hash_preservavel(row[1])]


def resumo_credenciais(db):
    """Contagens por situação, sem expor o conteúdo armazenado."""
    total, nulas = db.execute("SELECT COUNT(*), COUNT(*) - COUNT(senha) FROM usuarios").fetchone()
    legadas = len(ids_com_credencial_legada(db))
    return {"usuarios": total, "hashes_validos": total - nulas - legadas, "sem_credencial": nulas,
            "legadas": legadas}


# Valor de PRAGMA user_version enquanto a limpeza física (etapa 2 de migrar_senhas.py) não termina.
# É gravado na mesma transação da invalidação e zerado só depois do VACUUM; a aplicação nunca usa
# user_version para outra coisa (bancos da loja têm 0).
LIMPEZA_PENDENTE = 0x53454E48


def versao_do_banco(db):
    return db.execute("PRAGMA user_version").fetchone()[0]


def limpeza_pendente(db):
    return versao_do_banco(db) == LIMPEZA_PENDENTE


def marcar_limpeza_pendente(db):
    db.execute(f"PRAGMA user_version = {LIMPEZA_PENDENTE:d}")


def concluir_limpeza(db):
    db.execute("PRAGMA user_version = 0")


def invalidar_credenciais(db, ids):
    """Remove a credencial (senha = NULL) dos IDs informados. Não confirma: a transação é do chamador."""
    alteradas = 0
    for usuario_id in ids:
        alteradas += db.execute("UPDATE usuarios SET senha = NULL WHERE id = ?", (usuario_id,)).rowcount
    return alteradas


def autenticar(db, email, senha):
    # O schema não impõe e-mail único: verifica cada cadastro com o e-mail, na ordem de criação.
    rows = db.execute(
        "SELECT id, nome, email, tipo, senha FROM usuarios WHERE email = ? ORDER BY id", (email,)
    ).fetchall()
    for row in rows:
        if _senha_confere(row["senha"], senha):
            return {"id": row["id"], "nome": row["nome"], "email": row["email"], "tipo": row["tipo"]}
    return None
