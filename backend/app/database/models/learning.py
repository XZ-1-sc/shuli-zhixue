from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, DATE, DATETIME, DECIMAL, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, LONGTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class PracticeRecord(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "practice_records"
    __table_args__ = (
        Index("idx_practice_records_task", "task_id"),
        Index("idx_practice_records_user_time", "user_id", "answered_at"),
        Index("idx_practice_records_question", "question_id"),
        Index("idx_practice_records_review", "review_status", "answered_at"),
        Index("idx_practice_records_assignment", "assignment_id", "assignment_attempt_id"),
        Index("idx_practice_records_reviewer", "reviewer_id", "reviewed_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    selected_answer: Mapped[str | None] = mapped_column(String(16))
    answer_text: Mapped[str | None] = mapped_column(LONGTEXT)
    is_correct: Mapped[int | None] = mapped_column(TINYINT(1))
    score: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 2))
    mistake_tags: Mapped[list | None] = mapped_column(JSON)
    time_spent_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    practice_mode: Mapped[str] = mapped_column(
        ENUM("daily", "chapter", "mock", "wrong_book", "custom", "assessment", "assignment"),
        nullable=False,
        server_default=text("'custom'"),
    )
    assignment_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignments.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    assignment_attempt_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignment_attempts.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    review_status: Mapped[str] = mapped_column(
        ENUM("auto_graded", "pending", "graded"), nullable=False, server_default=text("'auto_graded'")
    )
    teacher_score: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 2))
    teacher_feedback: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME)
    correction_required: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))
    answered_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class UserGoalSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_goal_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uk_user_goal_settings_user"),)

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    target_course: Mapped[str] = mapped_column(String(128), nullable=False, server_default=text("'高等数学'"))
    target_stage: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'大一'"))
    weekly_hours: Mapped[Decimal] = mapped_column(DECIMAL(4, 1), nullable=False, server_default=text("'8.0'"))
    exam_date: Mapped[date | None] = mapped_column(DATE)


class LearningPlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_plans"
    __table_args__ = (
        Index("idx_learning_plans_user", "user_id"),
        Index("idx_learning_plans_stage_course", "stage", "course"),
    )

    user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    course: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class ChatMessage(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("idx_chat_messages_user_time", "user_id", "created_at"),
        Index("idx_chat_messages_session_time", "session_id", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(ENUM("user", "assistant"), nullable=False)
    content: Mapped[str] = mapped_column(LONGTEXT, nullable=False)


class NegotiationLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "negotiation_log"
    __table_args__ = (
        Index("idx_negotiation_log_conversation", "conversation_id", "round_no"),
        Index("idx_negotiation_log_user_time", "user_id", "created_at"),
        Index("idx_negotiation_log_speaker_type", "speaker", "message_type"),
    )

    conversation_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    round_no: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    speaker: Mapped[str] = mapped_column(ENUM("diagnostician", "strategist", "orchestrator"), nullable=False)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    needs_rediagnosis: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))


class LLMCallLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "llm_call_log"
    __table_args__ = (
        Index("idx_llm_call_log_conversation", "conversation_id", "created_at"),
        Index("idx_llm_call_log_agent_time", "agent_name", "created_at"),
    )

    conversation_id: Mapped[str | None] = mapped_column(CHAR(36))
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    total_tokens: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text)
