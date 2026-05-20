"""Add revision_count to orders.

Revision ID: 20260520_0003
Revises: 20260519_0002
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = '20260520_0003'
down_revision = '20260519_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'orders',
        sa.Column('revision_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('orders', 'revision_count')
