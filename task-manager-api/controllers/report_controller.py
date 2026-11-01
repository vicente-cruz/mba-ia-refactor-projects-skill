"""Relatórios: agregações delegadas aos models, sem consultas por item."""
from datetime import timedelta

from controllers.task_controller import completion_rate
from errors import NotFoundError
from models.category import Category
from models.clock import utc_now
from models.task import DONE_STATUS, HIGH_PRIORITY_MAX, Task
from models.user import User

RECENT_ACTIVITY_DAYS = 7


def summary_report():
    now = utc_now()
    by_status = Task.count_by_status()
    overdue_tasks = [task for task in Task.all_ordered() if task.is_overdue(now)]
    since = now - timedelta(days=RECENT_ACTIVITY_DAYS)
    productivity = [{
        'user_id': user.id,
        'user_name': user.name,
        'total_tasks': total,
        'completed_tasks': completed,
        'completion_rate': completion_rate(completed, total),
    } for user, total, completed in User.list_with_task_stats()]
    return {
        'generated_at': str(utc_now()),
        'overview': {
            'total_tasks': Task.count_all(),
            'total_users': User.count_all(),
            'total_categories': Category.count_all(),
        },
        'tasks_by_status': by_status,
        'tasks_by_priority': Task.count_by_priority(),
        'overdue': {
            'count': len(overdue_tasks),
            'tasks': [{
                'id': task.id,
                'title': task.title,
                'due_date': str(task.due_date),
                'days_overdue': task.days_overdue(now),
            } for task in overdue_tasks],
        },
        'recent_activity': {
            'tasks_created_last_7_days': Task.count_created_since(since),
            'tasks_completed_last_7_days': Task.count_done_updated_since(since),
        },
        'user_productivity': productivity,
    }


def user_report(user_id):
    user = User.find_by_id(user_id)
    if user is None:
        raise NotFoundError('Usuário não encontrado')
    tasks = Task.for_user(user_id)
    now = utc_now()
    counts = {status: 0 for status in ('done', 'pending', 'in_progress', 'cancelled')}
    for task in tasks:
        if task.status in counts:
            counts[task.status] += 1
    total = len(tasks)
    return {
        'user': {'id': user.id, 'name': user.name, 'email': user.email},
        'statistics': {
            'total_tasks': total,
            'done': counts[DONE_STATUS],
            'pending': counts['pending'],
            'in_progress': counts['in_progress'],
            'cancelled': counts['cancelled'],
            'overdue': sum(1 for task in tasks if task.is_overdue(now)),
            'high_priority': sum(1 for task in tasks if task.priority is not None and task.priority <= HIGH_PRIORITY_MAX),
            'completion_rate': completion_rate(counts[DONE_STATUS], total),
        },
    }
