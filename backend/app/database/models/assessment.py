from datetime import datetime

from sqlalchemy import CHAR, DATETIME, ForeignKey, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class UploadedFile(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uk_uploaded_files_storage"),
        Index("idx_uploaded_files_user_time", "user_id", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(768), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    width: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    height: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)


class AnswerAttachment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "answer_attachments"
    __table_args__ = (
        UniqueConstraint("uploaded_file_id", name="uk_answer_attachments_file"),
        Index("idx_answer_attachments_record", "practice_record_id", "sort_order"),
    )

    practice_record_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("practice_records.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    uploaded_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("uploaded_files.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("1"))


class AssessmentSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (
        UniqueConstraint("task_id", name="uk_assessment_sessions_task"),
        Index("idx_assessment_sessions_user_status", "user_id", "status", "started_at"),
    )

    task_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        ENUM("in_progress", "completed", "abandoned"), nullable=False, server_default=text("'in_progress'")
    )
    question_count: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    plan_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME)


class AssessmentSessionQuestion(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "assessment_session_questions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_id", name="uk_assessment_question"),
        UniqueConstraint("assessment_id", "sort_order", name="uk_assessment_order"),
        Index("idx_assessment_question_record", "practice_record_id"),
    )

    assessment_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assessment_sessions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False)
    practice_record_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("practice_records.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    answered_at: Mapped[datetime | None] = mapped_column(DATETIME)
