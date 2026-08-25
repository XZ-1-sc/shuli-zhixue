from datetime import datetime

from sqlalchemy import ForeignKey, Index, JSON, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin


class Conversation(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("participant_a", "participant_b", "relation", name="uk_conv_pair"),
        Index("idx_conv_last", "last_message_at"),
        Index("idx_conv_participant_a", "participant_a", "relation"),
        Index("idx_conv_participant_b", "participant_b", "relation"),
    )

    participant_a: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    participant_b: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(
        ENUM("teacher_student", "student_student"), nullable=False
    )
    last_message_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)


class Message(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_msg_conv_time", "conversation_id", "created_at"),
        Index("idx_msg_sender_unread", "sender_id", "is_read", "created_at"),
    )

    conversation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("conversations.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    message_type: Mapped[str] = mapped_column(
        ENUM("chat", "advice"), nullable=False, server_default=text("'chat'")
    )
    content: Mapped[str | None] = mapped_column(Text)
    attachment_ids: Mapped[list | None] = mapped_column(JSON)
    question_ref: Mapped[dict | None] = mapped_column(JSON)
    is_read: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))
