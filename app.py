import os
import uuid
import secrets
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from sqlalchemy.dialects.postgresql import JSON

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(hours=8)

# Конфигурация загрузки файлов
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///edo_ldpr.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------------- МОДЕЛИ -------------------------
class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    head_id = db.Column(db.String, nullable=True)

class User(db.Model):
    __tablename__ = 'users'
    uid = db.Column(db.String, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='executor')
    department_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(50), default='Нормальный')
    status = db.Column(db.String(100), default='Черновик')
    created_by = db.Column(db.String, nullable=False)
    creator_name = db.Column(db.String(200), nullable=True)
    assigned_department_id = db.Column(db.String, nullable=True)
    assigned_executor_id = db.Column(db.String, nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    result = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderHistory(db.Model):
    __tablename__ = 'order_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.String, nullable=False)
    action = db.Column(db.String(200), nullable=False)
    user_name = db.Column(db.String(200))
    user_role = db.Column(db.String(50))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String, nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.String, nullable=False)
    user_name = db.Column(db.String(200), nullable=False)
    user_role = db.Column(db.String(50))
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrderFile(db.Model):
    __tablename__ = 'order_files'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.String, nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------- ИНИЦИАЛИЗАЦИЯ БД -------------------------
def init_db():
    db.create_all()
    if User.query.count() == 0:
        departments = [('dept-1','Центральный аппарат'),('dept-2','Юридический отдел'),
                       ('dept-3','Организационный отдел'),('dept-4','Информационный отдел')]
        for d_id, d_name in departments:
            if db.session.get(Department, d_id) is None:
                db.session.add(Department(id=d_id, name=d_name))
        db.session.commit()
        users_data = [
            ('u-admin','Администратор','admin@ldpr.ru','admin','admin123','admin',None),
            ('u-sec','Секретарь','sec@ldpr.ru','secretary','sec123','secretary',None),
            ('u-head-central','Руководитель ЦА','headca@ldpr.ru','head_central','head123','head_central','dept-1'),
            ('u-head-dept','Начальник отдела','headdept@ldpr.ru','head_department','head123','head_department','dept-2'),
            ('u-ast','Помощник','ast@ldpr.ru','assistant','ast123','assistant',None),
            ('u-exec','Исполнитель','exec@ldpr.ru','executor','exec123','executor','dept-2')
        ]
        for uid, full_name, email, username, plain_pwd, role, dept_id in users_data:
            if db.session.get(User, uid) is None:
                hashed = generate_password_hash(plain_pwd)
                db.session.add(User(uid=uid, full_name=full_name, email=email, username=username,
                                    password=hashed, role=role, department_id=dept_id))
        db.session.commit()

with app.app_context():
    init_db()

# ------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ УВЕДОМЛЕНИЙ -------------------------
def create_notification(user_id, message, link=None):
    notif = Notification(user_id=user_id, message=message, link=link)
    db.session.add(notif)
    db.session.commit()

def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()

# ------------------------- ДЕКОРАТОРЫ -------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in roles:
                flash('Недостаточно прав', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.context_processor
def inject_user():
    user = None
    unread = 0
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        unread = get_unread_count(session['user_id'])
    return {'current_user': user, 'unread_count': unread}

# ------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------------
def get_orders_for_user():
    user_id = session['user_id']
    role = session['user_role']
    dept_id = session.get('department_id')
    query = Order.query.order_by(Order.created_at.desc())
    if role == 'admin':
        return query.all()
    elif role == 'assistant':
        return query.filter_by(created_by=user_id).all()
    elif role == 'head_department' and dept_id:
        return query.filter_by(assigned_department_id=dept_id).all()
    elif role == 'executor':
        return query.filter_by(assigned_executor_id=user_id).all()
    else:
        return query.all()

def get_stats():
    orders = get_orders_for_user()
    today = datetime.utcnow().date()
    return {
        'total': len(orders),
        'pending': sum(1 for o in orders if o.status == 'На утверждении'),
        'approved': sum(1 for o in orders if o.status == 'Утверждено'),
        'in_work': sum(1 for o in orders if o.status == 'В работе'),
        'overdue': sum(1 for o in orders if o.deadline and o.deadline < today and o.status not in ['Закрыто','Отклонено'])
    }

def get_overdue_orders():
    today = datetime.utcnow().date()
    orders = get_orders_for_user()
    return [o for o in orders if o.deadline and o.deadline < today and o.status not in ['Закрыто','Отклонено']]

# ------------------------- МАРШРУТЫ -------------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
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

@app.route('/')
@login_required
def dashboard():
    stats = get_stats()
    orders = get_orders_for_user()[:5]
    overdue = get_overdue_orders()[:5]
    return render_template('dashboard.html', stats=stats, orders=orders, overdue=overdue)

@app.route('/orders')
@login_required
def orders():
    all_orders = get_orders_for_user()
    status_filter = request.args.get('status', 'Все')
    search = request.args.get('search', '').lower()
    priority_filter = request.args.get('priority', 'Все')
    overdue_filter = request.args.get('overdue', '')
    filtered = all_orders
    if status_filter != 'Все':
        filtered = [o for o in filtered if o.status == status_filter]
    if priority_filter != 'Все':
        filtered = [o for o in filtered if o.priority == priority_filter]
    if search:
        filtered = [o for o in filtered if search in o.title.lower() or (o.content and search in o.content.lower())]
    if overdue_filter == 'yes':
        today = datetime.utcnow().date()
        filtered = [o for o in filtered if o.deadline and o.deadline < today and o.status not in ['Закрыто','Отклонено']]
    statuses = ['Черновик','На утверждении','Утверждено','В отделе','Назначен исполнитель',
                'В работе','Готово к проверке','Подтверждено','На доработке','Закрыто','Отклонено']
    priorities = ['Низкий','Нормальный','Высокий','Срочный']
    return render_template('orders.html', orders=filtered, statuses=statuses, priorities=priorities,
                           overdue_filter=overdue_filter, now=datetime.utcnow())

@app.route('/orders/export')
@login_required
def export_orders():
    try:
        orders = get_orders_for_user()
        data = []
        for o in orders:
            data.append({
                'ID': o.id,
                'Название': o.title,
                'Приоритет': o.priority,
                'Статус': o.status,
                'Срок': o.deadline.strftime('%Y-%m-%d') if o.deadline else '',
                'Автор': o.creator_name,
                'Создано': o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else '',
                'Исполнитель': o.assigned_executor_id or ''
            })
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Распоряжения')
        output.seek(0)
        return send_file(output, download_name='orders_export.xlsx', as_attachment=True,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Ошибка экспорта: {str(e)}', 'danger')
        return redirect(url_for('orders'))

@app.route('/orders/create', methods=['POST'])
@login_required
@role_required('assistant')
def create_order():
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    if not title or not content:
        flash('Заголовок и содержание обязательны', 'danger')
        return redirect(url_for('orders'))
    order_id = 'ord-'+str(uuid.uuid4())[:8]
    is_draft = request.form.get('is_draft') == '1'
    status = 'Черновик' if is_draft else 'На утверждении'
    user = db.session.get(User, session['user_id'])
    deadline_str = request.form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    new_order = Order(id=order_id, title=title, content=content,
                      priority=request.form.get('priority','Нормальный'),
                      status=status, created_by=session['user_id'],
                      creator_name=user.full_name, deadline=deadline)
    db.session.add(new_order)
    db.session.commit()
    history = OrderHistory(order_id=order_id, action='Создание', user_name=user.full_name,
                           user_role=session['user_role'], details=f'Статус: {status}')
    db.session.add(history)
    db.session.commit()
    # Уведомление руководителю ЦА
    heads = User.query.filter_by(role='head_central').all()
    for h in heads:
        create_notification(h.uid, f'Новое распоряжение "{title}" ожидает утверждения', f'/orders/{order_id}')
    flash('Распоряжение создано', 'success')
    return redirect(url_for('orders'))

@app.route('/orders/<order_id>')
@login_required
def order_details(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Не найдено', 'danger')
        return redirect(url_for('orders'))
    history = OrderHistory.query.filter_by(order_id=order_id).order_by(OrderHistory.created_at.desc()).all()
    departments = Department.query.all()
    dept_users = User.query.filter_by(department_id=order.assigned_department_id).all() if order.assigned_department_id else []
    comments = Comment.query.filter_by(order_id=order_id).order_by(Comment.created_at.asc()).all()
    files = OrderFile.query.filter_by(order_id=order_id).all()
    return render_template('order_details.html', order=order, history=history,
                           departments=departments, dept_users=dept_users,
                           comments=comments, files=files)

@app.route('/orders/<order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Не найдено', 'danger')
        return redirect(url_for('orders'))
    new_status = request.form.get('status')
    comment = request.form.get('comment', '')
    user = db.session.get(User, session['user_id'])
    role = session['user_role']
    cur = order.status
    allowed = False
    extra = {}
    if role == 'head_central' and cur == 'На утверждении' and new_status in ('Утверждено','Отклонено'):
        allowed = True
        # уведомления помощнику
        assistant = User.query.filter_by(uid=order.created_by).first()
        if assistant:
            msg = f'Распоряжение "{order.title}" {new_status.lower()}'
            create_notification(assistant.uid, msg, f'/orders/{order_id}')
        # если утверждено, секретарю
        if new_status == 'Утверждено':
            secs = User.query.filter_by(role='secretary').all()
            for s in secs:
                create_notification(s.uid, f'Распоряжение "{order.title}" утверждено, назначьте отдел', f'/orders/{order_id}')
    elif role == 'secretary' and cur == 'Утверждено' and request.form.get('department_id'):
        allowed = True
        new_status = 'В отделе'
        extra['assigned_department_id'] = request.form['department_id']
        # уведомление начальнику отдела
        dept_head = User.query.filter_by(department_id=extra['assigned_department_id'], role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Распоряжение "{order.title}" ожидает назначения исполнителя', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'В отделе' and request.form.get('executor_id'):
        allowed = True
        new_status = 'Назначен исполнитель'
        extra['assigned_executor_id'] = request.form['executor_id']
        # уведомление исполнителю
        executor = User.query.filter_by(uid=extra['assigned_executor_id']).first()
        if executor:
            create_notification(executor.uid, f'Вам назначено распоряжение "{order.title}"', f'/orders/{order_id}')
    elif role == 'executor' and cur == 'Назначен исполнитель' and order.assigned_executor_id == session['user_id']:
        allowed = True
        new_status = 'В работе'
        # уведомление начальнику отдела
        dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Исполнитель приступил к работе над "{order.title}"', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'Готово к проверке' and new_status == 'Подтверждено':
        allowed = True
        # уведомление руководителю ЦА
        heads = User.query.filter_by(role='head_central').all()
        for h in heads:
            create_notification(h.uid, f'Распоряжение "{order.title}" выполнено, ожидает закрытия', f'/orders/{order_id}')
    elif role == 'head_central' and cur == 'Подтверждено' and new_status == 'Закрыто':
        allowed = True
        # уведомление всем участникам
        participants = set()
        participants.add(order.created_by)
        if order.assigned_executor_id:
            participants.add(order.assigned_executor_id)
        if order.assigned_department_id:
            dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
            if dept_head:
                participants.add(dept_head.uid)
        for p in participants:
            create_notification(p, f'Распоряжение "{order.title}" закрыто', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'Готово к проверке' and new_status == 'На доработке':
        allowed = True
        if order.assigned_executor_id:
            create_notification(order.assigned_executor_id, f'Распоряжение "{order.title}" отправлено на доработку', f'/orders/{order_id}')
    elif role == 'head_central' and cur == 'Подтверждено' and new_status == 'На доработке':
        allowed = True
        if order.assigned_department_id:
            dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
            if dept_head:
                create_notification(dept_head.uid, f'Распоряжение "{order.title}" возвращено на доработку', f'/orders/{order_id}')
        if order.assigned_executor_id:
            create_notification(order.assigned_executor_id, f'Распоряжение "{order.title}" возвращено на доработку', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'Готово к проверке' and new_status == 'Отклонено':
        allowed = True
        if order.assigned_executor_id:
            create_notification(order.assigned_executor_id, f'Распоряжение "{order.title}" отклонено начальником отдела', f'/orders/{order_id}')
    elif role == 'assistant' and cur == 'На утверждении' and new_status == 'Отозвано':
        allowed = True
        heads = User.query.filter_by(role='head_central').all()
        for h in heads:
            create_notification(h.uid, f'Распоряжение "{order.title}" отозвано автором', f'/orders/{order_id}')
    if allowed:
        for k,v in extra.items():
            setattr(order, k, v)
        order.status = new_status
        db.session.commit()
        history = OrderHistory(order_id=order_id, action='Изменение статуса', user_name=user.full_name,
                               user_role=role, details=f'Статус: {new_status}' + (f' ({comment})' if comment else ''))
        db.session.add(history)
        db.session.commit()
        flash('Статус обновлён', 'success')
    else:
        flash('Действие запрещено', 'danger')
    return redirect(url_for('order_details', order_id=order_id))

@app.route('/orders/<order_id>/submit', methods=['POST'])
@login_required
def submit_order_result(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Не найдено', 'danger')
        return redirect(url_for('orders'))
    if session['user_role'] != 'executor' or order.status != 'В работе' or order.assigned_executor_id != session['user_id']:
        flash('Действие запрещено', 'danger')
        return redirect(url_for('order_details', order_id=order_id))
    res = request.form.get('result_content','').strip()
    if not res:
        flash('Опишите результат', 'warning')
        return redirect(url_for('order_details', order_id=order_id))
    result_data = {'content': res, 'submittedAt': datetime.utcnow().isoformat(), 'submittedBy': session['user_id']}
    order.status = 'Готово к проверке'
    order.result = result_data
    db.session.commit()
    user = db.session.get(User, session['user_id'])
    history = OrderHistory(order_id=order_id, action='Сдача работы', user_name=user.full_name,
                           user_role=session['user_role'], details='Работа сдана на проверку')
    db.session.add(history)
    db.session.commit()
    # уведомление начальнику отдела
    if order.assigned_department_id:
        dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Распоряжение "{order.title}" ожидает проверки', f'/orders/{order_id}')
    flash('Работа сдана', 'success')
    return redirect(url_for('order_details', order_id=order_id))

# ------------------------- КОММЕНТАРИИ -------------------------
@app.route('/orders/<order_id>/comment', methods=['POST'])
@login_required
def add_comment(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Не найдено', 'danger')
        return redirect(url_for('orders'))
    text = request.form.get('comment_text', '').strip()
    if not text:
        flash('Текст комментария не может быть пустым', 'warning')
        return redirect(url_for('order_details', order_id=order_id))
    user = db.session.get(User, session['user_id'])
    comment = Comment(order_id=order_id, user_name=user.full_name, user_role=user.role, text=text)
    db.session.add(comment)
    db.session.commit()
    flash('Комментарий добавлен', 'success')
    return redirect(url_for('order_details', order_id=order_id))

# ------------------------- ПРИКРЕПЛЁННЫЕ ФАЙЛЫ -------------------------
@app.route('/orders/<order_id>/upload', methods=['POST'])
@login_required
def upload_file(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Не найдено', 'danger')
        return redirect(url_for('orders'))
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('order_details', order_id=order_id))
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('order_details', order_id=order_id))
    if file and allowed_file(file.filename):
        original_name = file.filename
        ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
        safe_name = secure_filename(f"{uuid.uuid4().hex}.{ext}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        file.save(filepath)
        order_file = OrderFile(order_id=order_id, filename=safe_name, original_name=original_name,
                               filepath=filepath, uploaded_by=session['user_id'])
        db.session.add(order_file)
        db.session.commit()
        flash('Файл загружен', 'success')
    else:
        flash('Недопустимый тип файла', 'danger')
    return redirect(url_for('order_details', order_id=order_id))

@app.route('/orders/file/<int:file_id>/download')
@login_required
def download_file(file_id):
    order_file = OrderFile.query.get(file_id)
    if not order_file:
        flash('Файл не найден', 'danger')
        return redirect(url_for('orders'))
    order = Order.query.get(order_file.order_id)
    if not order:
        flash('Распоряжение не найдено', 'danger')
        return redirect(url_for('orders'))
    return send_file(order_file.filepath, download_name=order_file.original_name, as_attachment=True)

# ------------------------- УВЕДОМЛЕНИЯ -------------------------
@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
    for n in notifs:
        if not n.is_read:
            n.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)

# ------------------------- ОСТАЛЬНЫЕ МАРШРУТЫ (отделы, админ) -------------------------
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
    department = db.session.get(Department, dept_id)
    users = User.query.filter_by(department_id=dept_id).all()
    orders = Order.query.filter_by(assigned_department_id=dept_id).order_by(Order.created_at.desc()).all()
    return render_template('department.html', department=department, users=users, orders=orders)

@app.route('/department/create', methods=['POST'])
@login_required
@role_required('admin')
def create_department():
    name = request.form.get('name','').strip()
    if not name:
        flash('Введите название отдела', 'danger')
        return redirect(url_for('department'))
    dept_id = 'dept-'+str(uuid.uuid4())[:8]
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
    full_name = request.form.get('full_name','').strip()
    email = request.form.get('email','').strip()
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    role = request.form.get('role','executor')
    dept = request.form.get('department_id') or None
    if not all([full_name, email, username, password]):
        flash('Заполните все поля', 'danger')
        return redirect(url_for('admin_panel'))
    uid = 'u-'+str(uuid.uuid4())[:8]
    hashed = generate_password_hash(password)
    if User.query.filter_by(username=username).first():
        flash('Логин уже существует', 'danger')
        return redirect(url_for('admin_panel'))
    new_user = User(uid=uid, full_name=full_name, email=email, username=username,
                    password=hashed, role=role, department_id=dept)
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

# ------------------------- ЗАПУСК -------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)