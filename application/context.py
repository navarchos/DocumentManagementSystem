from flask import session

from app import app, db
from application.models import User
from application.notifications_utils import get_unread_count


@app.context_processor
def inject_user():
    user = None
    unread = 0
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        unread = get_unread_count(session['user_id'])
    return {'current_user': user, 'unread_count': unread}
