"""Add pgvector extension, RAG document/chunk tables and chat history tables.

Revision ID: 20260519_0002
Revises: 20260518_0001
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


revision = '20260519_0002'
down_revision = '20260518_0001'
branch_labels = None
depends_on = None


EMBEDDING_DIM = 256


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # RAG features require PostgreSQL with pgvector; skip on other engines.
        return

    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        'rag_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('order_file_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('indexed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_type', 'order_id', 'order_file_id', name='uq_rag_documents_source'),
    )
    op.create_index('ix_rag_documents_order_id', 'rag_documents', ['order_id'])

    op.create_table(
        'rag_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'document_id',
            sa.Integer(),
            sa.ForeignKey('rag_documents.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('order_file_id', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(EMBEDDING_DIM) if Vector is not None else sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rag_chunks_order_id', 'rag_chunks', ['order_id'])
    op.create_index('ix_rag_chunks_document_id', 'rag_chunks', ['document_id'])
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_hnsw '
        'ON rag_chunks USING hnsw (embedding vector_cosine_ops)'
    )

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'session_id',
            sa.Integer(),
            sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.execute('DROP INDEX IF EXISTS ix_rag_chunks_embedding_hnsw')
    op.drop_index('ix_rag_chunks_document_id', table_name='rag_chunks')
    op.drop_index('ix_rag_chunks_order_id', table_name='rag_chunks')
    op.drop_table('rag_chunks')
    op.drop_index('ix_rag_documents_order_id', table_name='rag_documents')
    op.drop_table('rag_documents')
