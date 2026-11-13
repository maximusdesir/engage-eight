"""add users.is_demo

Throwaway accounts created by POST /auth/demo, purged after 24 hours.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 09:49:54.992952
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_demo', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_demo')
