from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from app import app
from application.models import User


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.uid
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            session['department_id'] = user.department_id
            flash(f'Добро пожаловать, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли', 'info')
    return redirect(url_for('login'))
