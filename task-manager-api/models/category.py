import re

from sqlalchemy import func

from database import db, fits_integer_column
from models.clock import utc_now

DEFAULT_COLOR = '#000000'
COLOR_PATTERN = re.compile(r'#[0-9A-Fa-f]{6}')  # usado com fullmatch


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    color = db.Column(db.String(7), default=DEFAULT_COLOR)
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'created_at': str(self.created_at),
        }

    @staticmethod
    def is_valid_color(value):
        return isinstance(value, str) and COLOR_PATTERN.fullmatch(value) is not None

    @classmethod
    def find_by_id(cls, category_id):
        if not fits_integer_column(category_id):
            return None
        return db.session.get(cls, category_id)

    @classmethod
    def count_all(cls):
        return db.session.query(func.count(cls.id)).scalar()

    @classmethod
    def list_with_task_counts(cls):
        """Categorias com a quantidade de tasks, em uma única consulta."""
        from models.task import Task
        rows = (db.session.query(cls, func.count(Task.id))
                .outerjoin(Task, Task.category_id == cls.id)
                .group_by(cls.id)
                .order_by(cls.id)
                .all())
        return rows
