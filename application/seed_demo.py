"""Demo orders with attachments from seed_data/files/."""

import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import mimetypes

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app import app, db
from application.file_utils import (
    allowed_file,
    build_storage_path,
    is_s3_storage_enabled,
    save_order_file,
)
from application.models import Comment, Order, OrderFile, OrderHistory, User

SEED_FILES_DIR = Path(__file__).resolve().parent.parent / 'seed_data' / 'files'
DEMO_ORDER_PREFIX = 'ord-seed-'


def _guess_order_fields(title: str, index: int):
    """Infer status, department and priority from document title."""
    lower = title.lower()
    if 'аналитическая' in lower:
        dept, creator = 'dept-4', 'u-sec'
        status = 'Закрыто' if '2023' in title else 'В работе'
        priority = 'Нормальный'
    elif 'обзор обращений' in lower:
        dept, creator = 'dept-2', 'u-head-dept'
        status = 'В работе' if '2025' in title else 'Закрыто'
        priority = 'Высокий' if '2025' in title else 'Нормальный'
    elif 'порядок' in lower or 'регламент' in lower:
        dept, creator = 'dept-3', 'u-ast'
        status = 'Утверждено'
        priority = 'Нормальный'
    elif 'решение' in lower:
        dept, creator = 'dept-1', 'u-head-central'
        status = 'На утверждении' if '2024' in title else 'Закрыто'
        priority = 'Высокий'
    elif 'прием' in lower or 'информация' in lower:
        dept, creator = 'dept-3', 'u-sec'
        status = 'Утверждено'
        priority = 'Нормальный'
    elif 'test' in lower:
        dept, creator = 'dept-2', 'u-exec'
        status = 'Черновик'
        priority = 'Низкий'
    else:
        dept, creator = 'dept-2', 'u-sec'
        status = 'В работе'
        priority = 'Нормальный'

    days_ago = 14 + index
    if '2023' in title:
        days_ago = 400 + index
    elif '2024' in title:
        days_ago = 180 + index
    elif '2025' in title:
        days_ago = 30 + index

    return {
        'assigned_department_id': dept,
        'created_by': creator,
        'status': status,
        'priority': priority,
        'days_ago': days_ago,
    }


def _list_seed_files():
    if not SEED_FILES_DIR.is_dir():
        return []
    files = [p for p in SEED_FILES_DIR.iterdir() if p.is_file()]
    return sorted(files, key=lambda p: p.name.lower())


def _attach_file(order_id, path: Path, uploaded_by: str):
    filename = path.name
    if not allowed_file(filename):
        app.logger.warning('Seed: unsupported file type %s', filename)
        return None
    if not is_s3_storage_enabled():
        app.logger.warning('Seed: S3 not configured, skip %s', filename)
        return None

    ext = filename.rsplit('.', 1)[1].lower()
    safe_name = secure_filename(f'{uuid.uuid4().hex}.{ext}')
    storage_path = build_storage_path(order_id, safe_name)
    mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    file_storage = FileStorage(
        stream=BytesIO(path.read_bytes()),
        filename=filename,
        content_type=mime,
    )
    save_order_file(file_storage, storage_path)
    record = OrderFile(
        order_id=order_id,
        filename=safe_name,
        original_name=filename,
        filepath=storage_path,
        uploaded_by=uploaded_by,
    )
    db.session.add(record)
    return record


def _clear_demo_orders():
    ids = [o.id for o in Order.query.filter(Order.id.like(f'{DEMO_ORDER_PREFIX}%')).all()]
    if not ids:
        return
    for model in (OrderFile, OrderHistory, Comment):
        db.session.query(model).filter(model.order_id.in_(ids)).delete(synchronize_session=False)
    Order.query.filter(Order.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()


def seed_demo_data(force=False):
    """Create one order per file in seed_data/files/ with that file attached."""
    files = _list_seed_files()
    if not files:
        print(f'No files in {SEED_FILES_DIR} — demo orders skipped.')
        return {'orders': 0, 'files': 0}

    existing = Order.query.filter(Order.id.like(f'{DEMO_ORDER_PREFIX}%')).count()
    if existing and not force:
        print(f'Demo orders already exist ({existing}). Run: flask seed-db --force')
        return {'orders': 0, 'skipped': True}

    if force:
        _clear_demo_orders()

    if User.query.count() == 0:
        print('No users in database — run seed users first.')
        return {'orders': 0}

    created = 0
    attached = 0
    for index, path in enumerate(files, start=1):
        order_id = f'{DEMO_ORDER_PREFIX}{index:03d}'
        title = path.stem
        meta = _guess_order_fields(title, index)
        creator = db.session.get(User, meta['created_by'])
        if not creator:
            creator = db.session.get(User, 'u-sec')

        content = (
            f'Демонстрационное распоряжение для документа «{title}». '
            f'Файл: {path.name}'
        )
        order = Order(
            id=order_id,
            title=title,
            content=content,
            priority=meta['priority'],
            status=meta['status'],
            created_by=creator.uid,
            creator_name=creator.full_name,
            assigned_department_id=meta['assigned_department_id'],
            assigned_executor_id='u-exec' if meta['status'] in ('В работе', 'Назначен исполнитель') else None,
            created_at=datetime.utcnow() - timedelta(days=meta['days_ago']),
        )
        db.session.add(order)
        db.session.add(OrderHistory(
            order_id=order_id,
            action='Создание',
            user_name=creator.full_name,
            user_role=creator.role,
            details=f'Статус: {meta["status"]} (seed)',
        ))
        if meta['status'] == 'Закрыто':
            closer = db.session.get(User, 'u-head-central') or creator
            db.session.add(OrderHistory(
                order_id=order_id,
                action='Закрытие',
                user_name=closer.full_name,
                user_role=closer.role,
                details='Статус: Закрыто (seed)',
            ))

        db.session.flush()
        if _attach_file(order_id, path, creator.uid):
            attached += 1
        created += 1

    db.session.commit()
    print(f'Demo: {created} orders, {attached} files uploaded from {SEED_FILES_DIR.name}/')
    if attached < created and not is_s3_storage_enabled():
        print('Configure S3 env vars to attach files (orders were still created).')
    return {'orders': created, 'files': attached}
