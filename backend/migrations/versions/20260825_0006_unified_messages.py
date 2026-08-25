"""add unified conversations and messages

Revision ID: 20260825_0006
Revises: 20260825_0005
Create Date: 2026-08-25
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260825_0006"
down_revision: str | Sequence[str] | None = "20260825_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or not inspector.has_table("conversations"):
        op.create_table(
            "conversations",
            sa.Column("participant_a", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("participant_b", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("relation", mysql.ENUM("teacher_student", "student_student"), nullable=False),
            sa.Column("last_message_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["participant_a"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["participant_b"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("participant_a", "participant_b", "relation", name="uk_conv_pair"),
        )
        op.create_index("idx_conv_last", "conversations", ["last_message_at"])
        op.create_index("idx_conv_participant_a", "conversations", ["participant_a", "relation"])
        op.create_index("idx_conv_participant_b", "conversations", ["participant_b", "relation"])

    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("conversation_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("sender_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("message_type", mysql.ENUM("chat", "advice"), server_default="chat", nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("attachment_ids", sa.JSON(), nullable=True),
            sa.Column("question_ref", sa.JSON(), nullable=True),
            sa.Column("is_read", mysql.TINYINT(display_width=1), server_default=sa.text("0"), nullable=False),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sender_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_msg_conv_time", "messages", ["conversation_id", "created_at"])
        op.create_index("idx_msg_sender_unread", "messages", ["sender_id", "is_read", "created_at"])

    if not offline and inspector.has_table("teacher_student_messages"):
        connection = op.get_bind()
        connection.execute(
            sa.text(
                """
                INSERT INTO conversations (participant_a,participant_b,relation,last_message_at,created_at)
                SELECT LEAST(teacher_id,student_id),GREATEST(teacher_id,student_id),'teacher_student',
                       MAX(created_at),MIN(created_at)
                FROM teacher_student_messages
                GROUP BY LEAST(teacher_id,student_id),GREATEST(teacher_id,student_id)
                ON DUPLICATE KEY UPDATE last_message_at=GREATEST(COALESCE(last_message_at,VALUES(last_message_at)),VALUES(last_message_at))
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO messages (conversation_id,sender_id,message_type,content,is_read,created_at)
                SELECT c.id,
                       CASE WHEN legacy.sender_role='teacher' THEN legacy.teacher_id ELSE legacy.student_id END,
                       legacy.message_type,legacy.content,legacy.is_read,legacy.created_at
                FROM teacher_student_messages legacy
                JOIN conversations c
                  ON c.participant_a=LEAST(legacy.teacher_id,legacy.student_id)
                 AND c.participant_b=GREATEST(legacy.teacher_id,legacy.student_id)
                 AND c.relation='teacher_student'
                WHERE NOT EXISTS (
                  SELECT 1 FROM messages current_message
                  WHERE current_message.conversation_id=c.id
                    AND current_message.sender_id=CASE WHEN legacy.sender_role='teacher' THEN legacy.teacher_id ELSE legacy.student_id END
                    AND current_message.created_at=legacy.created_at
                    AND COALESCE(current_message.content,'')=COALESCE(legacy.content,'')
                )
                """
            )
        )


def downgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or inspector.has_table("messages"):
        op.drop_table("messages")
    if offline or inspector.has_table("conversations"):
        op.drop_table("conversations")
