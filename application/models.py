from datetime import datetime

from app import db

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - allow running without pgvector installed
    Vector = None


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
    result = db.Column(db.JSON, nullable=True)
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


_RAG_EMBEDDING_DIM = 256
_VectorType = Vector(_RAG_EMBEDDING_DIM) if Vector is not None else db.Text


class RagDocument(db.Model):
    __tablename__ = 'rag_documents'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_type = db.Column(db.String(50), nullable=False)
    order_id = db.Column(db.String, nullable=False, index=True)
    order_file_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(500), nullable=True)
    content_hash = db.Column(db.String(64), nullable=False)
    indexed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('source_type', 'order_id', 'order_file_id', name='uq_rag_documents_source'),
    )


class RagChunk(db.Model):
    __tablename__ = 'rag_chunks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.Integer, db.ForeignKey('rag_documents.id', ondelete='CASCADE'), nullable=False)
    order_id = db.Column(db.String, nullable=False, index=True)
    source_type = db.Column(db.String(50), nullable=False)
    order_file_id = db.Column(db.Integer, nullable=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, nullable=True)
    embedding = db.Column(_VectorType, nullable=True)


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sources = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
