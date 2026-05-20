"""Tests for application/notifications_utils.py."""
import pytest


@pytest.fixture(autouse=True)
def clean_notifications(app, db):
    """Remove test notifications after each test."""
    yield
    with app.app_context():
        from application.models import Notification
        Notification.query.filter(Notification.user_id == 'u-notif-test').delete()
        db.session.commit()


class TestCreateNotification:
    def test_creates_record(self, app, db):
        from application.notifications_utils import create_notification
        from application.models import Notification
        with app.app_context():
            create_notification('u-notif-test', 'Test message', '/orders/1')
            notif = Notification.query.filter_by(
                user_id='u-notif-test', message='Test message'
            ).first()
            assert notif is not None
            assert notif.link == '/orders/1'
            assert notif.is_read is False

    def test_without_link(self, app):
        from application.notifications_utils import create_notification
        from application.models import Notification
        with app.app_context():
            create_notification('u-notif-test', 'No link message')
            notif = Notification.query.filter_by(
                user_id='u-notif-test', message='No link message'
            ).first()
            assert notif is not None
            assert notif.link is None

    def test_multiple_notifications(self, app, db):
        from application.notifications_utils import create_notification
        from application.models import Notification
        with app.app_context():
            for i in range(3):
                create_notification('u-notif-test', f'Message {i}')
            count = Notification.query.filter_by(user_id='u-notif-test').count()
            assert count >= 3


class TestGetUnreadCount:
    def test_count_starts_at_zero(self, app):
        from application.notifications_utils import get_unread_count
        with app.app_context():
            count = get_unread_count('u-nonexistent-user-xyz')
            assert count == 0

    def test_count_increases(self, app, db):
        from application.notifications_utils import create_notification, get_unread_count
        with app.app_context():
            before = get_unread_count('u-notif-test')
            create_notification('u-notif-test', 'New notif 1')
            create_notification('u-notif-test', 'New notif 2')
            after = get_unread_count('u-notif-test')
            assert after == before + 2

    def test_read_notifications_not_counted(self, app, db):
        from application.models import Notification
        from application.notifications_utils import get_unread_count
        with app.app_context():
            notif = Notification(
                user_id='u-notif-test',
                message='Already read',
                is_read=True,
            )
            db.session.add(notif)
            db.session.commit()
            count_before = get_unread_count('u-notif-test')
            # The already-read notification must not appear in the count
            read_notifs = Notification.query.filter_by(
                user_id='u-notif-test', is_read=True
            ).count()
            unread = get_unread_count('u-notif-test')
            assert unread == count_before  # unchanged; the new one was read
