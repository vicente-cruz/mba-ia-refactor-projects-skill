"""Script para popular o banco com dados iniciais.

Apaga e recria usuários, categorias e tasks numa única transação: em qualquer
falha nada é gravado. As senhas vêm do ambiente (sem valores padrão):

    SECRET_KEY=... SEED_ADMIN_PASSWORD=... SEED_USER_PASSWORD=... \\
    SEED_MANAGER_PASSWORD=... python seed.py
"""
import os
import sys
from datetime import timedelta

from sqlalchemy import delete

from database import db
from models.category import Category
from models.clock import utc_now
from models.task import Task
from models.user import PASSWORD_MIN_LENGTH, User

SEED_PASSWORD_VARS = ('SEED_ADMIN_PASSWORD', 'SEED_USER_PASSWORD', 'SEED_MANAGER_PASSWORD')

SEED_USERS = (
    {'name': 'João Silva', 'email': 'joao@email.com', 'role': 'admin', 'password_var': 'SEED_ADMIN_PASSWORD'},
    {'name': 'Maria Santos', 'email': 'maria@email.com', 'role': 'user', 'password_var': 'SEED_USER_PASSWORD'},
    {'name': 'Pedro Oliveira', 'email': 'pedro@email.com', 'role': 'manager', 'password_var': 'SEED_MANAGER_PASSWORD'},
)

SEED_CATEGORIES = (
    {'name': 'Backend', 'description': 'Tarefas de backend', 'color': '#3498db'},
    {'name': 'Frontend', 'description': 'Tarefas de frontend', 'color': '#2ecc71'},
    {'name': 'DevOps', 'description': 'Tarefas de infraestrutura', 'color': '#e74c3c'},
    {'name': 'Bug', 'description': 'Correção de bugs', 'color': '#e67e22'},
)

# user/category: índice em SEED_USERS/SEED_CATEGORIES; due_in_days relativo a agora.
SEED_TASKS = (
    {'title': 'Implementar autenticação JWT', 'description': 'Adicionar autenticação real com JWT', 'status': 'pending', 'priority': 1, 'user': 0, 'category': 0, 'due_in_days': -3},
    {'title': 'Criar tela de login', 'description': 'Tela de login responsiva', 'status': 'in_progress', 'priority': 2, 'user': 1, 'category': 1, 'due_in_days': 5},
    {'title': 'Configurar CI/CD', 'description': 'Pipeline com GitHub Actions', 'status': 'done', 'priority': 2, 'user': 2, 'category': 2, 'tags': 'devops,ci,github'},
    {'title': 'Corrigir bug no filtro de busca', 'description': 'Filtro não funciona com caracteres especiais', 'status': 'pending', 'priority': 1, 'user': 0, 'category': 3, 'due_in_days': -1},
    {'title': 'Adicionar paginação na API', 'description': 'Endpoints retornam todos os registros', 'status': 'pending', 'priority': 3, 'user': 0, 'category': 0, 'due_in_days': 10},
    {'title': 'Escrever testes unitários', 'description': 'Cobertura mínima de 80%', 'status': 'pending', 'priority': 2, 'user': 1, 'category': 0},
    {'title': 'Documentar API com Swagger', 'description': 'Gerar documentação automática', 'status': 'cancelled', 'priority': 4, 'user': 2, 'category': 0},
    {'title': 'Refatorar models', 'description': 'Melhorar organização dos models', 'status': 'in_progress', 'priority': 3, 'user': 1, 'category': 0, 'tags': 'refactor,tech-debt'},
    {'title': 'Configurar monitoramento', 'description': 'Prometheus + Grafana', 'status': 'pending', 'priority': 4, 'user': 2, 'category': 2, 'due_in_days': 20},
    {'title': 'Melhorar validações de input', 'description': 'Usar marshmallow ou pydantic', 'status': 'pending', 'priority': 3, 'user': 0, 'category': 0, 'tags': 'improvement,validation'},
)


class SeedConfigError(Exception):
    pass


def read_seed_passwords(environ):
    """Valida todas as senhas antes de qualquer acesso ao banco. A mensagem só nomeia variáveis."""
    invalid = [name for name in SEED_PASSWORD_VARS
               if not isinstance(environ.get(name), str) or len(environ.get(name)) < PASSWORD_MIN_LENGTH]
    if invalid:
        raise SeedConfigError(
            f'variáveis ausentes ou com menos de {PASSWORD_MIN_LENGTH} caracteres: {", ".join(invalid)}')
    return {name: environ[name] for name in SEED_PASSWORD_VARS}


def seed_data(app, passwords):
    with app.app_context():
        try:
            db.session.execute(delete(Task))
            db.session.execute(delete(User))
            db.session.execute(delete(Category))

            users = []
            for spec in SEED_USERS:
                user = User(name=spec['name'], email=spec['email'], role=spec['role'])
                user.set_password(passwords[spec['password_var']])
                db.session.add(user)
                users.append(user)
            categories = []
            for spec in SEED_CATEGORIES:
                category = Category(**spec)
                db.session.add(category)
                categories.append(category)
            db.session.flush()  # IDs de usuários e categorias, ainda sem commit

            now = utc_now()
            for spec in SEED_TASKS:
                task = Task(title=spec['title'], description=spec['description'], status=spec['status'],
                            priority=spec['priority'], user_id=users[spec['user']].id,
                            category_id=categories[spec['category']].id, tags=spec.get('tags'))
                if 'due_in_days' in spec:
                    task.due_date = now + timedelta(days=spec['due_in_days'])
                db.session.add(task)
            db.session.commit()
        except BaseException:
            db.session.rollback()
            raise
        print('Seed concluído com sucesso!')
        print(f'  {User.count_all()} usuários')
        print(f'  {Category.count_all()} categorias')
        print(f'  {Task.count_all()} tasks')


def main():
    from app import create_app
    from config import ConfigError
    try:
        passwords = read_seed_passwords(os.environ)
    except SeedConfigError as error:
        print(f'Seed não executado: {error}', file=sys.stderr)
        return 1
    try:
        app = create_app()
    except ConfigError as error:
        print(f'Erro de configuração: {error}', file=sys.stderr)
        return 2
    try:
        seed_data(app, passwords)
    except Exception as error:
        print(f'Seed falhou e nada foi gravado ({type(error).__name__})', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
