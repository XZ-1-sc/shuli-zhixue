from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class UserNote(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_notes"
    __table_args__ = (Index("idx_user_notes_user_time", "user_id", "updated_at"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    course: Mapped[str | None] = mapped_column(String(128))
    knowledge_tag: Mapped[str | None] = mapped_column(String(160))


class NoteAttachment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "note_attachments"
    __table_args__ = (
        UniqueConstraint("uploaded_file_id", name="uk_note_attachments_file"),
        Index("idx_note_attachments_note", "note_id", "sort_order"),
    )

    note_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("user_notes.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    uploaded_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("uploaded_files.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("1"))


class UserNotification(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "user_notifications"
    __table_args__ = (Index("idx_user_notifications_user_time", "user_id", "is_read", "created_at"),)

    user_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    type: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'system'"))
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(512))
    is_read: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))


class LearningResource(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "learning_resources"
    __table_args__ = (
        Index("idx_learning_resources_stage_course", "stage", "course"),
        Index("idx_learning_resources_type", "resource_type"),
    )

    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    course: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(512))
    difficulty: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("2"))
