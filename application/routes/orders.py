import uuid
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from app import app, db
from application.decorators import login_required, role_required
from application.file_utils import allowed_file, build_storage_path, is_s3_storage_enabled, get_s3_client, save_order_file, send_order_file
from application.models import Comment, Department, Order, OrderFile, OrderHistory, User
from application.notifications_utils import create_notification
from application.services import get_orders_for_user


def _schedule_reindex_order(order_id):
    from application.rag.indexer import schedule_reindex_order
    schedule_reindex_order(order_id)


def _schedule_reindex_file(order_file_id):
    from application.rag.indexer import schedule_reindex_file
    schedule_reindex_file(order_file_id)


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
        filtered = [
            o for o in filtered
            if o.deadline and o.deadline < today and o.status not in ['Закрыто', 'Отклонено']
        ]
    statuses = [
        'Черновик',
        'На утверждении',
        'Утверждено',
        'В отделе',
        'Назначен исполнитель',
        'В работе',
        'Готово к проверке',
        'Подтверждено',
        'На доработке',
        'Закрыто',
        'Отклонено',
    ]
    priorities = ['Низкий', 'Нормальный', 'Высокий', 'Срочный']
    return render_template(
        'orders.html',
        orders=filtered,
        statuses=statuses,
        priorities=priorities,
        overdue_filter=overdue_filter,
        now=datetime.utcnow(),
    )


@app.route('/orders/export')
@login_required
def export_orders():
    try:
        orders_list = get_orders_for_user()
        data = []
        for o in orders_list:
            data.append({
                'ID': o.id,
                'Название': o.title,
                'Приоритет': o.priority,
                'Статус': o.status,
                'Срок': o.deadline.strftime('%Y-%m-%d') if o.deadline else '',
                'Автор': o.creator_name,
                'Создано': o.created_at.strftime('%Y-%m-%d %H:%M') if o.created_at else '',
                'Исполнитель': o.assigned_executor_id or '',
            })
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Распоряжения')
        output.seek(0)
        return send_file(
            output,
            download_name='orders_export.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as e:
        flash(f'Ошибка экспорта: {str(e)}', 'danger')
        return redirect(url_for('orders'))


@app.route('/orders/create', methods=['POST'])
@login_required
@role_required('assistant')
def create_order():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        flash('Заголовок и содержание обязательны', 'danger')
        return redirect(url_for('orders'))

    order_id = 'ord-' + str(uuid.uuid4())[:8]
    is_draft = request.form.get('is_draft') == '1'
    status = 'Черновик' if is_draft else 'На утверждении'
    user = db.session.get(User, session['user_id'])
    deadline_str = request.form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
    new_order = Order(
        id=order_id,
        title=title,
        content=content,
        priority=request.form.get('priority', 'Нормальный'),
        status=status,
        created_by=session['user_id'],
        creator_name=user.full_name,
        deadline=deadline,
    )
    db.session.add(new_order)
    db.session.commit()

    history = OrderHistory(
        order_id=order_id,
        action='Создание',
        user_name=user.full_name,
        user_role=session['user_role'],
        details=f'Статус: {status}',
    )
    db.session.add(history)
    db.session.commit()

    heads = User.query.filter_by(role='head_central').all()
    for h in heads:
        create_notification(h.uid, f'Новое распоряжение "{title}" ожидает утверждения', f'/orders/{order_id}')
    _schedule_reindex_order(order_id)
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
    return render_template(
        'order_details.html',
        order=order,
        history=history,
        departments=departments,
        dept_users=dept_users,
        comments=comments,
        files=files,
    )


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

    if role == 'head_central' and cur == 'На утверждении' and new_status in ('Утверждено', 'Отклонено'):
        allowed = True
        assistant = User.query.filter_by(uid=order.created_by).first()
        if assistant:
            msg = f'Распоряжение "{order.title}" {new_status.lower()}'
            create_notification(assistant.uid, msg, f'/orders/{order_id}')
        if new_status == 'Утверждено':
            secs = User.query.filter_by(role='secretary').all()
            for s in secs:
                create_notification(s.uid, f'Распоряжение "{order.title}" утверждено, назначьте отдел', f'/orders/{order_id}')
    elif role == 'secretary' and cur == 'Утверждено' and request.form.get('department_id'):
        allowed = True
        new_status = 'В отделе'
        extra['assigned_department_id'] = request.form['department_id']
        dept_head = User.query.filter_by(department_id=extra['assigned_department_id'], role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Распоряжение "{order.title}" ожидает назначения исполнителя', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'В отделе' and request.form.get('executor_id'):
        allowed = True
        new_status = 'Назначен исполнитель'
        extra['assigned_executor_id'] = request.form['executor_id']
        executor = User.query.filter_by(uid=extra['assigned_executor_id']).first()
        if executor:
            create_notification(executor.uid, f'Вам назначено распоряжение "{order.title}"', f'/orders/{order_id}')
    elif role == 'executor' and cur == 'Назначен исполнитель' and order.assigned_executor_id == session['user_id']:
        allowed = True
        new_status = 'В работе'
        dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Исполнитель приступил к работе над "{order.title}"', f'/orders/{order_id}')
    elif role == 'executor' and cur == 'На доработке' and order.assigned_executor_id == session['user_id']:
        allowed = True
        new_status = 'В работе'
        order.revision_count = (order.revision_count or 0) + 1
        dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Исполнитель возобновил работу над "{order.title}"', f'/orders/{order_id}')
        create_notification(order.created_by, f'Исполнитель приступил к доработке "{order.title}"', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'На доработке' and request.form.get('executor_id'):
        allowed = True
        new_status = 'Назначен исполнитель'
        old_executor_id = order.assigned_executor_id
        extra['assigned_executor_id'] = request.form['executor_id']
        new_exec = User.query.filter_by(uid=extra['assigned_executor_id']).first()
        if new_exec:
            create_notification(new_exec.uid, f'Вам переназначено распоряжение "{order.title}"', f'/orders/{order_id}')
        if old_executor_id and old_executor_id != extra['assigned_executor_id']:
            create_notification(old_executor_id, f'Распоряжение "{order.title}" переназначено другому исполнителю', f'/orders/{order_id}')
    elif role == 'head_department' and cur == 'Готово к проверке' and new_status == 'Подтверждено':
        allowed = True
        heads = User.query.filter_by(role='head_central').all()
        for h in heads:
            create_notification(h.uid, f'Распоряжение "{order.title}" выполнено, ожидает закрытия', f'/orders/{order_id}')
    elif role == 'head_central' and cur == 'Подтверждено' and new_status == 'Закрыто':
        allowed = True
        participants = {order.created_by}
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
        for k, v in extra.items():
            setattr(order, k, v)
        order.status = new_status
        db.session.commit()
        history = OrderHistory(
            order_id=order_id,
            action='Изменение статуса',
            user_name=user.full_name,
            user_role=role,
            details=f'Статус: {new_status}' + (f' ({comment})' if comment else ''),
        )
        db.session.add(history)
        db.session.commit()
        _schedule_reindex_order(order_id)
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

    res = request.form.get('result_content', '').strip()
    if not res:
        flash('Опишите результат', 'warning')
        return redirect(url_for('order_details', order_id=order_id))

    existing = order.result if isinstance(order.result, list) else []
    rev_num = len(existing) + 1
    entry = {'revision': rev_num, 'content': res, 'submittedAt': datetime.utcnow().isoformat(), 'submittedBy': session['user_id']}
    order.result = existing + [entry]
    order.status = 'Готово к проверке'
    db.session.commit()

    user = db.session.get(User, session['user_id'])
    history = OrderHistory(
        order_id=order_id,
        action='Сдача работы',
        user_name=user.full_name,
        user_role=session['user_role'],
        details='Работа сдана на проверку',
    )
    db.session.add(history)
    db.session.commit()
    _schedule_reindex_order(order_id)

    if order.assigned_department_id:
        dept_head = User.query.filter_by(department_id=order.assigned_department_id, role='head_department').first()
        if dept_head:
            create_notification(dept_head.uid, f'Распоряжение "{order.title}" ожидает проверки', f'/orders/{order_id}')
    flash('Работа сдана', 'success')
    return redirect(url_for('order_details', order_id=order_id))


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
        storage_path = build_storage_path(order_id, safe_name)
        try:
            save_order_file(file, storage_path)
        except RuntimeError:
            app.logger.exception('Failed to upload order file to S3')
            flash('Не удалось загрузить файл в S3-хранилище. Проверьте настройки и доступ к бакету.', 'danger')
            return redirect(url_for('order_details', order_id=order_id))

        order_file = OrderFile(
            order_id=order_id,
            filename=safe_name,
            original_name=original_name,
            filepath=storage_path,
            uploaded_by=session['user_id'],
        )
        db.session.add(order_file)
        db.session.commit()
        _schedule_reindex_file(order_file.id)
        flash('Файл загружен', 'success')
    else:
        flash('Недопустимый тип файла', 'danger')
    return redirect(url_for('order_details', order_id=order_id))


@app.route('/orders/<order_id>/delete', methods=['POST'])
@login_required
@role_required('head_central')
def delete_order(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        flash('Распоряжение не найдено', 'danger')
        return redirect(url_for('orders'))

    if order.status != 'Закрыто':
        flash('Удаление разрешено только для закрытых распоряжений', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    password = request.form.get('confirm_password', '')
    user = db.session.get(User, session['user_id'])
    if not user or not check_password_hash(user.password, password):
        flash('Неверный пароль. Удаление отменено', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    files = OrderFile.query.filter_by(order_id=order_id).all()
    if is_s3_storage_enabled():
        s3 = get_s3_client()
        bucket = app.config['S3_BUCKET_NAME']
        for f in files:
            try:
                s3.delete_object(Bucket=bucket, Key=f.filepath)
            except Exception:
                app.logger.warning('Could not delete S3 object %s', f.filepath)

    for f in files:
        db.session.delete(f)

    try:
        from application.models import RagChunk, RagDocument
        rag_docs = RagDocument.query.filter_by(order_id=order_id).all()
        for doc in rag_docs:
            RagChunk.query.filter_by(document_id=doc.id).delete()
            db.session.delete(doc)
    except Exception:
        pass

    Comment.query.filter_by(order_id=order_id).delete()
    OrderHistory.query.filter_by(order_id=order_id).delete()
    db.session.delete(order)
    db.session.commit()

    flash(f'Распоряжение «{order.title}» и все его файлы удалены', 'success')
    return redirect(url_for('orders'))


@app.route('/orders/file/<int:file_id>/download')
@login_required
def download_file(file_id):
    order_file = db.session.get(OrderFile, file_id)
    if not order_file:
        flash('Файл не найден', 'danger')
        return redirect(url_for('orders'))
    order = db.session.get(Order, order_file.order_id)
    if not order:
        flash('Распоряжение не найдено', 'danger')
        return redirect(url_for('orders'))
    try:
        return send_order_file(order_file)
    except FileNotFoundError:
        flash('Файл не найден в хранилище', 'danger')
        return redirect(url_for('order_details', order_id=order.id))
