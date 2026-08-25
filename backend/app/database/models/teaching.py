from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, DATETIME, DECIMAL, ForeignKey, Index, JSON, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, LONGTEXT, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class Class(IdMixin, TimestampMixin, Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("invite_code", name="uk_classes_invite_code"),
        UniqueConstraint("teacher_id", "name", name="uk_classes_teacher_name"),
        Index("idx_classes_teacher_status", "teacher_id", "status"),
    )

    teacher_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    course: Mapped[str] = mapped_column(String(128), nullable=False)
    invite_code: Mapped[str] = mapped_column(CHAR(8, collation="ascii_bin"), nullable=False)
    status: Mapped[str] = mapped_column(
        ENUM("active", "archived"), nullable=False, server_default=text("'active'")
    )


class ClassMember(IdMixin, Base):
    __tablename__ = "class_members"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uk_class_members_class_student"),
        Index("idx_class_members_student_status", "student_id", "status"),
        Index("idx_class_members_class_status", "class_id", "status"),
    )

    class_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        ENUM("active", "removed"), nullable=False, server_default=text("'active'")
    )
    joined_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    removed_at: Mapped[datetime | None] = mapped_column(DATETIME)


class Assignment(IdMixin, TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index("idx_assignments_teacher_status", "teacher_id", "status", "created_at"),
        Index("idx_assignments_class_status_due", "class_id", "status", "due_at"),
    )

    teacher_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        ENUM("draft", "published", "closed", "archived"), nullable=False, server_default=text("'draft'")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DATETIME)
    due_at: Mapped[datetime | None] = mapped_column(DATETIME)
    time_limit_minutes: Mapped[int | None] = mapped_column(SMALLINT(unsigned=True))
    max_attempts: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("1"))
    show_analysis_after_submit: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("1"))
    total_score: Mapped[Decimal] = mapped_column(DECIMAL(7, 2), nullable=False, server_default=text("'0.00'"))
    published_at: Mapped[datetime | None] = mapped_column(DATETIME)


class AssignmentQuestion(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "assignment_questions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "question_id", name="uk_assignment_question"),
        UniqueConstraint("assignment_id", "sort_order", name="uk_assignment_question_order"),
        Index("idx_assignment_questions_question", "question_id"),
    )

    assignment_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignments.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False)
    points: Mapped[Decimal] = mapped_column(DECIMAL(6, 2), nullable=False, server_default=text("'10.00'"))
    required: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("1"))


class AssignmentAttempt(IdMixin, TimestampMixin, Base):
    __tablename__ = "assignment_attempts"
    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id", "attempt_no", name="uk_assignment_attempt"),
        Index("idx_assignment_attempts_student_status", "user_id", "status", "updated_at"),
        Index("idx_assignment_attempts_assignment_status", "assignment_id", "status", "submitted_at"),
    )

    assignment_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignments.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(
        ENUM("in_progress", "submitted", "grading", "graded", "returned"),
        nullable=False,
        server_default=text("'in_progress'"),
    )
    started_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    submitted_at: Mapped[datetime | None] = mapped_column(DATETIME)
    graded_at: Mapped[datetime | None] = mapped_column(DATETIME)
    total_score: Mapped[Decimal | None] = mapped_column(DECIMAL(7, 2))
    max_score: Mapped[Decimal] = mapped_column(DECIMAL(7, 2), nullable=False, server_default=text("'0.00'"))
    teacher_feedback: Mapped[str | None] = mapped_column(Text)


class AssignmentAnswer(IdMixin, TimestampMixin, Base):
    __tablename__ = "assignment_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "assignment_question_id", name="uk_assignment_answer_question"),
        UniqueConstraint("practice_record_id", name="uk_assignment_answer_record"),
        Index("idx_assignment_answers_review", "review_status", "answered_at"),
    )

    attempt_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignment_attempts.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    assignment_question_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("assignment_questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    practice_record_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("practice_records.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    selected_answer: Mapped[str | None] = mapped_column(String(16))
    answer_text: Mapped[str | None] = mapped_column(LONGTEXT)
    attachment_ids: Mapped[list | None] = mapped_column(JSON)
    time_spent_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    is_correct: Mapped[int | None] = mapped_column(TINYINT(1))
    score: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 2))
    review_status: Mapped[str] = mapped_column(
        ENUM("saved", "auto_graded", "pending", "graded", "returned"),
        nullable=False,
        server_default=text("'saved'"),
    )
    teacher_feedback: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DATETIME)
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME)




class TeacherStudentMessage(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "teacher_student_messages"
    __table_args__ = (
        Index("idx_tsm_pair_time", "teacher_id", "student_id", "created_at"),
        Index("idx_tsm_student_read", "student_id", "is_read", "created_at"),
        Index("idx_tsm_teacher_read", "teacher_id", "is_read", "created_at"),
    )

    teacher_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    class_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    sender_role: Mapped[str] = mapped_column(
        ENUM("teacher", "student"), nullable=False
    )
    message_type: Mapped[str] = mapped_column(
        ENUM("chat", "advice"), nullable=False, server_default=text("'chat'")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))


class AdviceDraft(IdMixin, TimestampMixin, Base):
    __tablename__ = "advice_drafts"
    __table_args__ = (
        Index("idx_advice_drafts_teacher_status", "teacher_id", "status"),
        Index("idx_advice_drafts_class_student", "class_id", "student_id", "status"),
    )

    teacher_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        ENUM("draft", "sent", "archived"), nullable=False, server_default=text("'draft'")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME)
