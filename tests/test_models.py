"""Tests for SQLAlchemy models defined in application/models.py."""
import uuid
from datetime import date, datetime

import pytest


@pytest.fixture(autouse=True)
def clean_db(db):
    """Roll back every test's changes so tests remain isolated."""
    yield
    db.session.rollback()


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class TestDepartment:
    def test_create(self, app, db):
        from application.models import Department
        with app.app_context():
            dept = Department(id='dept-test', name='Test Department')
            db.session.add(dept)
            db.session.flush()
            assert db.session.get(Department, 'dept-test') is not None

    def test_name_required(self, app, db):
        from sqlalchemy.exc import IntegrityError
        from application.models import Department
        with app.app_context():
            dept = Department(id='dept-bad', name=None)
            db.session.add(dept)
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class TestUser:
    def test_seed_users_exist(self, app):
        from application.models import User
        with app.app_context():
            assert User.query.count() >= 6

    def test_user_roles(self, app):
        from application.models import User
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            assert admin is not None
            assert admin.role == 'admin'

    def test_create_user(self, app, db):
        from application.models import User
        with app.app_context():
            uid = f'u-test-{uuid.uuid4().hex[:8]}'
            user = User(
                uid=uid,
                full_name='Test User',
                email=f'{uid}@example.com',
                username=uid,
                password='hashed',
                role='executor',
            )
            db.session.add(user)
            db.session.flush()
            found = db.session.get(User, uid)
            assert found.full_name == 'Test User'
            db.session.rollback()

    def test_email_unique(self, app, db):
        from sqlalchemy.exc import IntegrityError
        from application.models import User
        with app.app_context():
            for i in range(2):
                db.session.add(User(
                    uid=f'u-dup-{i}',
                    full_name='Dup',
                    email='dup@example.com',
                    username=f'dup_{i}',
                    password='x',
                    role='executor',
                ))
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class TestOrder:
    def test_create_order(self, app, db):
        from application.models import Order
        with app.app_context():
            order = Order(
                id='ord-test-1',
                title='Test Order',
                content='Some content',
                created_by='u-admin',
                creator_name='Admin',
            )
            db.session.add(order)
            db.session.flush()
            found = db.session.get(Order, 'ord-test-1')
            assert found.title == 'Test Order'
            assert found.status == 'Черновик'
            assert found.priority == 'Нормальный'
            db.session.rollback()

    def test_default_status_and_priority(self, app, db):
        from application.models import Order
        with app.app_context():
            order = Order(id='ord-def', title='Default Fields', created_by='u-admin')
            db.session.add(order)
            db.session.flush()
            assert order.status == 'Черновик'
            assert order.priority == 'Нормальный'
            assert order.revision_count == 0
            db.session.rollback()


# ---------------------------------------------------------------------------
# OrderHistory
# ---------------------------------------------------------------------------

class TestOrderHistory:
    def test_create_history_entry(self, app, db):
        from application.models import Order, OrderHistory
        with app.app_context():
            order = Order(id='ord-hist-1', title='H', created_by='u-admin')
            db.session.add(order)
            db.session.flush()
            entry = OrderHistory(
                order_id='ord-hist-1',
                action='Создано',
                user_name='Admin',
                user_role='admin',
            )
            db.session.add(entry)
            db.session.flush()
            assert entry.id is not None
            db.session.rollback()


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class TestNotification:
    def test_create_notification(self, app, db):
        from application.models import Notification
        with app.app_context():
            notif = Notification(user_id='u-admin', message='Hello', link='/orders')
            db.session.add(notif)
            db.session.flush()
            assert notif.is_read is False
            db.session.rollback()


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class TestComment:
    def test_create_comment(self, app, db):
        from application.models import Comment
        with app.app_context():
            comment = Comment(
                order_id='ord-test',
                user_name='Executor',
                user_role='executor',
                text='Great work!',
            )
            db.session.add(comment)
            db.session.flush()
            assert comment.id is not None
            db.session.rollback()


# ---------------------------------------------------------------------------
# OrderFile
# ---------------------------------------------------------------------------

class TestOrderFile:
    def test_create_file(self, app, db):
        from application.models import OrderFile
        with app.app_context():
            f = OrderFile(
                order_id='ord-test',
                filename='doc.pdf',
                original_name='document.pdf',
                filepath='orders/ord-test/doc.pdf',
                uploaded_by='u-admin',
            )
            db.session.add(f)
            db.session.flush()
            assert f.id is not None
            db.session.rollback()
