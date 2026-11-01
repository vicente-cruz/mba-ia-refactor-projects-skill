from sqlalchemy import case, func

from database import db, fits_integer_column
from models.clock import utc_now

VALID_STATUSES = ('pending', 'in_progress', 'done', 'cancelled')
CLOSED_STATUSES = ('done', 'cancelled')
DONE_STATUS = 'done'
DEFAULT_STATUS = 'pending'
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3
HIGH_PRIORITY_MAX = 2
PRIORITY_LABELS = {1: 'critical', 2: 'high', 3: 'medium', 4: 'low', 5: 'minimal'}
TITLE_MIN_LENGTH = 3
TITLE_MAX_LENGTH = 200
DUE_DATE_FORMAT = '%Y-%m-%d'
TAG_SEPARATOR = ','


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default=DEFAULT_STATUS)
    priority = db.Column(db.Integer, default=DEFAULT_PRIORITY)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    due_date = db.Column(db.DateTime, nullable=True)
    tags = db.Column(db.String(500), nullable=True)

    user = db.relationship('User', backref='tasks')
    category = db.relationship('Category', backref='tasks')

    # ------------------------------------------------------------ regras
    def tag_list(self):
        return self.tags.split(TAG_SEPARATOR) if self.tags else []

    def is_overdue(self, now=None):
        if not self.due_date:
            return False
        now = now or utc_now()
        return self.due_date < now and self.status not in CLOSED_STATUSES

    def days_overdue(self, now):
        return (now - self.due_date).days

    # ------------------------------------------------------------ representações
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'user_id': self.user_id,
            'category_id': self.category_id,
            'created_at': str(self.created_at),
            'updated_at': str(self.updated_at),
            'due_date': str(self.due_date) if self.due_date else None,
            'tags': self.tag_list(),
        }

    def to_dict_with_overdue(self, now=None):
        data = self.to_dict()
        data['overdue'] = self.is_overdue(now)
        return data

    def to_user_task_dict(self, now=None):
        """Subconjunto usado por GET /users/<id>/tasks."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'created_at': str(self.created_at),
            'due_date': str(self.due_date) if self.due_date else None,
            'overdue': self.is_overdue(now),
        }

    # ------------------------------------------------------------ consultas
    @classmethod
    def find_by_id(cls, task_id):
        if not fits_integer_column(task_id):
            return None
        return db.session.get(cls, task_id)

    @classmethod
    def all_ordered(cls):
        return cls.query.order_by(cls.id).all()

    @classmethod
    def for_user(cls, user_id):
        return cls.query.filter_by(user_id=user_id).order_by(cls.id).all()

    @classmethod
    def list_with_relation_names(cls):
        """Tasks com nome do usuário e da categoria em uma única consulta (sem N+1)."""
        from models.category import Category
        from models.user import User
        return (db.session.query(cls, User.name, Category.name)
                .outerjoin(User, User.id == cls.user_id)
                .outerjoin(Category, Category.id == cls.category_id)
                .order_by(cls.id)
                .all())

    @classmethod
    def search(cls, text=None, status=None, priority=None, user_id=None):
        for value in (priority, user_id):
            if value is not None and not fits_integer_column(value):
                return []  # nenhum valor armazenado pode estar fora da faixa
        query = cls.query
        if text:
            query = query.filter(db.or_(cls.title.like(f'%{text}%'), cls.description.like(f'%{text}%')))
        if status:
            query = query.filter(cls.status == status)
        if priority is not None:
            query = query.filter(cls.priority == priority)
        if user_id is not None:
            query = query.filter(cls.user_id == user_id)
        return query.order_by(cls.id).all()

    @classmethod
    def count_all(cls):
        return db.session.query(func.count(cls.id)).scalar()

    @classmethod
    def count_by_status(cls):
        rows = db.session.query(cls.status, func.count(cls.id)).group_by(cls.status).all()
        found = dict(rows)
        return {status: found.get(status, 0) for status in VALID_STATUSES}

    @classmethod
    def count_by_priority(cls):
        rows = db.session.query(cls.priority, func.count(cls.id)).group_by(cls.priority).all()
        found = dict(rows)
        return {label: found.get(value, 0) for value, label in PRIORITY_LABELS.items()}

    @classmethod
    def count_created_since(cls, moment):
        return db.session.query(func.count(cls.id)).filter(cls.created_at >= moment).scalar()

    @classmethod
    def count_done_updated_since(cls, moment):
        return (db.session.query(func.count(cls.id))
                .filter(cls.status == DONE_STATUS, cls.updated_at >= moment).scalar())

    @classmethod
    def done_count_expression(cls):
        return func.coalesce(func.sum(case((cls.status == DONE_STATUS, 1), else_=0)), 0)
