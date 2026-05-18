from datetime import datetime

from flask import session

from application.models import Order


def get_orders_for_user():
    user_id = session['user_id']
    role = session['user_role']
    dept_id = session.get('department_id')
    query = Order.query.order_by(Order.created_at.desc())

    if role == 'admin':
        return query.all()
    if role == 'assistant':
        return query.filter_by(created_by=user_id).all()
    if role == 'head_department' and dept_id:
        return query.filter_by(assigned_department_id=dept_id).all()
    if role == 'executor':
        return query.filter_by(assigned_executor_id=user_id).all()

    return query.all()


def get_stats():
    orders = get_orders_for_user()
    today = datetime.utcnow().date()
    return {
        'total': len(orders),
        'pending': sum(1 for o in orders if o.status == 'На утверждении'),
        'approved': sum(1 for o in orders if o.status == 'Утверждено'),
        'in_work': sum(1 for o in orders if o.status == 'В работе'),
        'overdue': sum(
            1 for o in orders
            if o.deadline and o.deadline < today and o.status not in ['Закрыто', 'Отклонено']
        ),
    }


def get_overdue_orders():
    today = datetime.utcnow().date()
    orders = get_orders_for_user()
    return [
        o for o in orders
        if o.deadline and o.deadline < today and o.status not in ['Закрыто', 'Отклонено']
    ]
