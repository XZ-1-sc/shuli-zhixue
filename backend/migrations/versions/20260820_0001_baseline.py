"""baseline all active math-brain tables

Revision ID: 20260820_0001
Revises:
Create Date: 2026-08-20
"""
from typing import Sequence

from alembic import op

from app.database.models import Base


revision: str = "20260820_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=not op.get_context().as_sql)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=not op.get_context().as_sql)
