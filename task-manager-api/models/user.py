import hmac
import hashlib
import re
import secrets

from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from database import db, fits_integer_column
from models.clock import utc_now

VALID_ROLES = ('user', 'admin', 'manager')
DEFAULT_ROLE = 'user'
ADMIN_ROLE = 'admin'
PASSWORD_MIN_LENGTH = 4
# Mesma regex e mesmo re.match do original (contrato preservado, inclusive '$' antes de '\n' final).
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$')
LEGACY_MD5_PATTERN = re.compile(r'[0-9a-f]{32}')  # usado com fullmatch


def generate_auth_nonce():
    """Identificador aleatório da instância da conta, embutido no token (campo sid)."""
    return secrets.token_urlsafe(32)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default=DEFAULT_ROLE)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    # Anulável no banco: a coluna é adicionada a bancos existentes por ALTER TABLE.
    auth_nonce = db.Column(db.String(64), nullable=True, default=generate_auth_nonce)

    # ------------------------------------------------------------ representação pública
    def to_dict(self):
        """Nunca inclui password nem auth_nonce."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'active': self.active,
            'created_at': str(self.created_at),
        }

    def to_summary_dict(self, task_count):
        data = self.to_dict()
        data['task_count'] = task_count
        return data

    # ------------------------------------------------------------ senha
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def change_password(self, password):
        """Troca a senha e revoga todos os tokens emitidos para a conta."""
        self.set_password(password)
        self.rotate_auth_nonce()

    def rotate_auth_nonce(self):
        self.auth_nonce = generate_auth_nonce()

    def ensure_auth_nonce(self):
        if not self.auth_nonce:
            self.rotate_auth_nonce()
            return True
        return False

    def verify_password(self, password):
        """Retorna (credencial_valida, precisa_regravar_hash). Hash malformado = inválido."""
        stored = self.password or ''
        if LEGACY_MD5_PATTERN.fullmatch(stored):
            candidate = hashlib.md5(password.encode()).hexdigest()
            return hmac.compare_digest(stored, candidate), True
        try:
            return check_password_hash(stored, password), False
        except (ValueError, TypeError, AttributeError):
            return False, False

    def is_admin(self):
        return self.role == ADMIN_ROLE

    @staticmethod
    def is_valid_email(value):
        return isinstance(value, str) and EMAIL_PATTERN.match(value) is not None

    # ------------------------------------------------------------ consultas
    @classmethod
    def find_by_id(cls, user_id):
        if not fits_integer_column(user_id):
            return None
        return db.session.get(cls, user_id)

    @classmethod
    def find_by_email(cls, email):
        return cls.query.filter_by(email=email).first()

    @classmethod
    def email_taken(cls, email, except_user_id=None):
        existing = cls.find_by_email(email)
        return existing is not None and existing.id != except_user_id

    @classmethod
    def count_all(cls):
        return db.session.query(func.count(cls.id)).scalar()

    @classmethod
    def list_with_task_counts(cls):
        from models.task import Task
        return (db.session.query(cls, func.count(Task.id))
                .outerjoin(Task, Task.user_id == cls.id)
                .group_by(cls.id)
                .order_by(cls.id)
                .all())

    @classmethod
    def list_with_task_stats(cls):
        """(user, total, concluídas) por usuário, em uma única consulta."""
        from models.task import Task
        return (db.session.query(cls, func.count(Task.id), Task.done_count_expression())
                .outerjoin(Task, Task.user_id == cls.id)
                .group_by(cls.id)
                .order_by(cls.id)
                .all())
