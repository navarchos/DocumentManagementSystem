from app import db
from application.models import Notification


def create_notification(user_id, message, link=None):
    notif = Notification(user_id=user_id, message=message, link=link)
    db.session.add(notif)
    db.session.commit()


def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()
