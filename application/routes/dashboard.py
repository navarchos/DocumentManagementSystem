from flask import render_template

from app import app
from application.decorators import login_required
from application.services import get_orders_for_user, get_overdue_orders, get_stats


@app.route('/')
@login_required
def dashboard():
    stats = get_stats()
    orders = get_orders_for_user()[:5]
    overdue = get_overdue_orders()[:5]
    return render_template('dashboard.html', stats=stats, orders=orders, overdue=overdue)
