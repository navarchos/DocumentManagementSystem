import uuid

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from app import app, db
from application.decorators import login_required, role_required
from application.models import Department, User


@app.route('/admin')
@login_required
@role_required('admin')
def admin_panel():
    users = User.query.all()
    departments = Department.query.all()
    return render_template('admin.html', users=users, departments=departments)


@app.route('/admin/users/create', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_user():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'executor')
    dept = request.form.get('department_id') or None
    if not all([full_name, email, username, password]):
        flash('Заполните все поля', 'danger')
        return redirect(url_for('admin_panel'))

    uid = 'u-' + str(uuid.uuid4())[:8]
    hashed = generate_password_hash(password)
    if User.query.filter_by(username=username).first():
        flash('Логин уже существует', 'danger')
        return redirect(url_for('admin_panel'))

    new_user = User(
        uid=uid,
        full_name=full_name,
        email=email,
        username=username,
        password=hashed,
        role=role,
        department_id=dept,
    )
    db.session.add(new_user)
    db.session.commit()
    flash('Пользователь создан', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/users/<uid>/edit', methods=['POST'])
@login_required
@role_required('admin')
def admin_edit_user(uid):
    user = db.session.get(User, uid)
    if not user:
        flash('Не найден', 'danger')
        return redirect(url_for('admin_panel'))
    user.full_name = request.form.get('full_name', user.full_name)
    user.email = request.form.get('email', user.email)
    user.role = request.form.get('role', user.role)
    user.department_id = request.form.get('department_id') or None
    new_password = request.form.get('password', '').strip()
    if new_password:
        user.password = generate_password_hash(new_password)
        flash('Пароль изменён', 'success')
    db.session.commit()
    flash('Данные обновлены', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/users/<uid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(uid):
    if uid == session['user_id']:
        flash('Нельзя удалить себя', 'danger')
        return redirect(url_for('admin_panel'))
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('Удалён', 'success')
    return redirect(url_for('admin_panel'))
