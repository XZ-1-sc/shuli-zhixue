"""add teacher messaging and advice workflow tables

Revision ID: 20260825_0005
Revises: 20260823_0004
Create Date: 2026-08-25
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260825_0005"
down_revision: str | Sequence[str] | None = "20260823_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or not inspector.has_table("teacher_student_messages"):
        op.create_table(
            "teacher_student_messages",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("student_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("sender_role", mysql.ENUM("teacher", "student"), nullable=False),
            sa.Column("message_type", mysql.ENUM("chat", "advice"), server_default="chat", nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_read", mysql.TINYINT(display_width=1), server_default=sa.text("0"), nullable=False),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_tsm_pair_time", "teacher_student_messages", ["teacher_id", "student_id", "created_at"])
        op.create_index("idx_tsm_student_read", "teacher_student_messages", ["student_id", "is_read", "created_at"])
        op.create_index("idx_tsm_teacher_read", "teacher_student_messages", ["teacher_id", "is_read", "created_at"])

    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or not inspector.has_table("advice_drafts"):
        op.create_table(
            "advice_drafts",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("student_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", mysql.ENUM("draft", "sent", "archived"), server_default="draft", nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_advice_drafts_teacher_status", "advice_drafts", ["teacher_id", "status"])
        op.create_index("idx_advice_drafts_class_student", "advice_drafts", ["class_id", "student_id", "status"])


def downgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or inspector.has_table("advice_drafts"):
        op.drop_table("advice_drafts")
    if offline or inspector.has_table("teacher_student_messages"):
        op.drop_table("teacher_student_messages")
