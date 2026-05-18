"""Initial PostgreSQL-ready schema.

Revision ID: 20260518_0001
Revises:
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa


revision = '20260518_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'departments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('head_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'users',
        sa.Column('uid', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('department_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )

    op.create_table(
        'orders',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('creator_name', sa.String(length=200), nullable=True),
        sa.Column('assigned_department_id', sa.String(), nullable=True),
        sa.Column('assigned_executor_id', sa.String(), nullable=True),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'order_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(length=200), nullable=False),
        sa.Column('user_name', sa.String(length=200), nullable=True),
        sa.Column('user_role', sa.String(length=50), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('link', sa.String(length=200), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('user_name', sa.String(length=200), nullable=False),
        sa.Column('user_role', sa.String(length=50), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'order_files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(length=200), nullable=False),
        sa.Column('original_name', sa.String(length=200), nullable=False),
        sa.Column('filepath', sa.String(length=500), nullable=False),
        sa.Column('uploaded_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('order_files')
    op.drop_table('comments')
    op.drop_table('notifications')
    op.drop_table('order_history')
    op.drop_table('orders')
    op.drop_table('users')
    op.drop_table('departments')
