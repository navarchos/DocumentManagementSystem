"""Chat blueprint: page, JSON message API and session management."""
import logging

from flask import jsonify, render_template, request, session

from app import app, db
from application.decorators import login_required
from application.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


def _rag_enabled() -> bool:
    is_supported = getattr(app, 'is_rag_supported', None)
    return bool(is_supported() if callable(is_supported) else False)


def _serialize_session(chat: ChatSession) -> dict:
    return {
        'id': chat.id,
        'title': chat.title or 'Новый чат',
        'updated_at': chat.updated_at.isoformat() if chat.updated_at else None,
    }


def _serialize_message(msg: ChatMessage) -> dict:
    return {
        'id': msg.id,
        'role': msg.role,
        'content': msg.content,
        'sources': msg.sources or [],
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
    }


@app.route('/chat')
@login_required
def chat_page():
    from application.rag.chat import list_sessions
    enabled = _rag_enabled()
    sessions = list_sessions(session['user_id']) if enabled else []
    return render_template(
        'chat.html',
        rag_enabled=enabled,
        chat_sessions=sessions,
    )


@app.route('/chat/sessions', methods=['GET'])
@login_required
def chat_list_sessions():
    from application.rag.chat import list_sessions
    if not _rag_enabled():
        return jsonify({'enabled': False, 'sessions': []})
    sessions = list_sessions(session['user_id'])
    return jsonify({
        'enabled': True,
        'sessions': [_serialize_session(s) for s in sessions],
    })


@app.route('/chat/sessions', methods=['POST'])
@login_required
def chat_create_session():
    if not _rag_enabled():
        return jsonify({'error': 'RAG is not enabled'}), 503
    chat = ChatSession(user_id=session['user_id'])
    db.session.add(chat)
    db.session.commit()
    return jsonify(_serialize_session(chat)), 201


@app.route('/chat/sessions/<int:session_id>', methods=['GET'])
@login_required
def chat_get_session(session_id):
    from application.rag.chat import list_messages
    chat = db.session.get(ChatSession, session_id)
    if not chat or chat.user_id != session['user_id']:
        return jsonify({'error': 'Not found'}), 404
    messages = list_messages(chat)
    return jsonify({
        'session': _serialize_session(chat),
        'messages': [_serialize_message(m) for m in messages],
    })


@app.route('/chat/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def chat_delete_session(session_id):
    chat = db.session.get(ChatSession, session_id)
    if not chat or chat.user_id != session['user_id']:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(chat)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    from application.rag.chat import answer, get_or_create_session
    if not _rag_enabled():
        return jsonify({
            'error': 'RAG-бот недоступен: требуется PostgreSQL c pgvector и Yandex API key.'
        }), 503
    payload = request.get_json(silent=True) or {}
    message_text = (payload.get('message') or '').strip()
    if not message_text:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400
    if len(message_text) > 4000:
        return jsonify({'error': 'Сообщение слишком длинное (>4000 символов)'}), 400

    session_id = payload.get('session_id')
    try:
        session_id_int = int(session_id) if session_id is not None else None
    except (TypeError, ValueError):
        session_id_int = None

    if session_id_int is not None:
        chat = db.session.get(ChatSession, session_id_int)
        if not chat or chat.user_id != session['user_id']:
            session_id_int = None

    chat = get_or_create_session(session['user_id'], session_id_int)
    try:
        result = answer(message_text, session_id=chat.id)
    except Exception:  # pragma: no cover - defensive
        logger.exception('Chat answer failed')
        return jsonify({'error': 'Внутренняя ошибка чат-бота'}), 500
    return jsonify(result)
