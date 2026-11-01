"""Extensão do banco, preparação do schema e commit com rollback."""
import logging
import secrets

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from errors import ConflictError, OperationError

db = SQLAlchemy()
logger = logging.getLogger('task_manager')

AUTH_NONCE_COLUMN = 'auth_nonce'
# Faixa do INTEGER do SQLite (64 bits com sinal). Valores fora dela não podem
# identificar nenhuma linha: buscas por ID devolvem "não encontrado" e filtros
# não casam com nada, em vez de OverflowError (500) no driver.
SQL_INTEGER_MIN = -(2 ** 63)
SQL_INTEGER_MAX = 2 ** 63 - 1


def fits_integer_column(value):
    return isinstance(value, int) and not isinstance(value, bool) and SQL_INTEGER_MIN <= value <= SQL_INTEGER_MAX
EMAIL_UNIQUE_MARKER = 'users.email'


def init_schema():
    """Cria as tabelas ausentes e aplica a migração aditiva de users.auth_nonce.

    db.create_all() não adiciona colunas a tabelas existentes; por isso a coluna
    é adicionada explicitamente em bancos criados pela versão anterior.
    """
    db.create_all()
    return _ensure_auth_nonce_column()


def _ensure_auth_nonce_column():
    engine = db.engine
    columns = {column['name'] for column in inspect(engine).get_columns('users')}
    if AUTH_NONCE_COLUMN in columns:
        return False
    if engine.dialect.name == 'sqlite':
        _migrate_sqlite(engine)
    else:
        _migrate_transactional(engine)
    logger.info('Migração aplicada: coluna users.%s adicionada', AUTH_NONCE_COLUMN)
    return True


def _migrate_sqlite(engine):
    """ALTER TABLE + preenchimento numa única transação explícita.

    O driver sqlite3 (modo legado) não abre transação antes de DDL: um ALTER TABLE
    emitido dentro de engine.begin() seria confirmado sozinho. Aqui o controle de
    transação é desligado do driver e BEGIN/COMMIT/ROLLBACK são emitidos à mão,
    de modo que uma falha no preenchimento desfaz também a criação da coluna.
    """
    raw = engine.raw_connection()
    try:
        driver_connection = raw.driver_connection
        previous_isolation = driver_connection.isolation_level
        driver_connection.isolation_level = None
        try:
            cursor = driver_connection.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            try:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {AUTH_NONCE_COLUMN} VARCHAR(64)')
                user_ids = [row[0] for row in cursor.execute('SELECT id FROM users').fetchall()]
                for user_id in user_ids:
                    cursor.execute(f'UPDATE users SET {AUTH_NONCE_COLUMN} = ? WHERE id = ?',
                                   (secrets.token_urlsafe(32), user_id))
                cursor.execute('COMMIT')
            except BaseException:
                cursor.execute('ROLLBACK')
                raise
        finally:
            driver_connection.isolation_level = previous_isolation
    finally:
        raw.close()


def _migrate_transactional(engine):
    """Bancos com DDL transacional (ex.: PostgreSQL). Não validado neste projeto."""
    with engine.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE users ADD COLUMN {AUTH_NONCE_COLUMN} VARCHAR(64)')
        user_ids = [row[0] for row in connection.exec_driver_sql('SELECT id FROM users')]
        for user_id in user_ids:
            connection.exec_driver_sql(f'UPDATE users SET {AUTH_NONCE_COLUMN} = %s WHERE id = %s',
                                       (secrets.token_urlsafe(32), user_id))


def commit_or_rollback(operation_message):
    """Confirma a operação; em falha, desfaz e converte em erro de domínio.

    Conflito na restrição users.email vira 409; demais falhas viram 500 com a
    mensagem da operação. Nenhum texto da exceção (que pode ter parâmetros) é logado.
    """
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        if EMAIL_UNIQUE_MARKER in str(getattr(error, 'orig', '')):
            logger.warning('Conflito de unicidade de email em "%s"', operation_message)
            raise ConflictError('Email já cadastrado') from None
        logger.warning('Falha de integridade em "%s"', operation_message)
        raise OperationError(operation_message) from None
    except SQLAlchemyError as error:
        db.session.rollback()
        logger.warning('Falha de persistência em "%s" (%s)', operation_message, type(error).__name__)
        raise OperationError(operation_message) from None
