import uuid

from flask import flash, redirect, render_template, request, session, url_for

from app import app, db
from application.decorators import login_required, role_required
from application.models import Department, Order, User


@app.route('/department')
@login_required
def department():
    if session.get('user_role') == 'admin':
        departments = Department.query.all()
        all_users = User.query.all()
        for d in departments:
            if d.head_id:
                head = db.session.get(User, d.head_id)
                d.head_name = head.full_name if head else None
            else:
                d.head_name = None
        return render_template('admin_departments.html', departments=departments, users=all_users)

    dept_id = session.get('department_id')
    if not dept_id:
        flash('У вас нет назначенного отдела', 'warning')
        return redirect(url_for('dashboard'))
    department_record = db.session.get(Department, dept_id)
    users = User.query.filter_by(department_id=dept_id).all()
    orders = Order.query.filter_by(assigned_department_id=dept_id).order_by(Order.created_at.desc()).all()
    return render_template('department.html', department=department_record, users=users, orders=orders)


@app.route('/department/create', methods=['POST'])
@login_required
@role_required('admin')
def create_department():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Введите название отдела', 'danger')
        return redirect(url_for('department'))
    dept_id = 'dept-' + str(uuid.uuid4())[:8]
    new_dept = Department(id=dept_id, name=name)
    db.session.add(new_dept)
    db.session.commit()
    flash('Отдел создан', 'success')
    return redirect(url_for('department'))


@app.route('/department/<dept_id>')
@login_required
@role_required('admin')
def department_details(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Отдел не найден', 'danger')
        return redirect(url_for('department'))
    users = User.query.filter_by(department_id=dept_id).all()
    orders = Order.query.filter_by(assigned_department_id=dept_id).order_by(Order.created_at.desc()).all()
    return render_template('department.html', department=dept, users=users, orders=orders)


@app.route('/admin/departments/<dept_id>/set_head', methods=['POST'])
@login_required
@role_required('admin')
def set_department_head(dept_id):
    head_id = request.form.get('head_id')
    if not head_id:
        flash('Выберите руководителя', 'danger')
        return redirect(url_for('department'))
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Отдел не найден', 'danger')
        return redirect(url_for('department'))
    dept.head_id = head_id
    db.session.commit()
    flash('Руководитель назначен', 'success')
    return redirect(url_for('department'))


@app.route('/admin/departments/<dept_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Отдел не найден', 'danger')
        return redirect(url_for('admin_panel'))
    users_in_dept = User.query.filter_by(department_id=dept_id).count()
    if users_in_dept > 0:
        flash('Нельзя удалить отдел, в котором есть сотрудники', 'danger')
        return redirect(url_for('admin_panel'))
    db.session.delete(dept)
    db.session.commit()
    flash('Отдел удалён', 'success')
    return redirect(url_for('admin_panel'))
