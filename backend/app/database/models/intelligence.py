from datetime import datetime
from decimal import Decimal

from sqlalchemy import DATETIME, DECIMAL, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class TeacherExperience(IdMixin, TimestampMixin, Base):
    __tablename__ = "teacher_experiences"
    __table_args__ = (Index("idx_teacher_experiences_lookup", "teacher_id", "knowledge_tag", "status"),)

    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"))
    question_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="SET NULL", onupdate="CASCADE"))
    knowledge_tag: Mapped[str | None] = mapped_column(String(160))
    experience_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(ENUM("active", "archived"), nullable=False, server_default=text("'active'"))
    usage_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))


class TeacherAIPreference(IdMixin, TimestampMixin, Base):
    __tablename__ = "teacher_ai_preferences"
    __table_args__ = (UniqueConstraint("teacher_id", name="uk_teacher_ai_preferences_teacher"),)

    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    tone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'清晰、鼓励、重方法'"))
    scoring_strictness: Mapped[str] = mapped_column(ENUM("lenient", "balanced", "strict"), nullable=False, server_default=text("'balanced'"))
    preferred_types: Mapped[list | None] = mapped_column(JSON)
    style_notes: Mapped[str | None] = mapped_column(Text)
    assistant_enabled: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("1"))


class TeachingRisk(IdMixin, Base):
    __tablename__ = "teaching_risks"
    __table_args__ = (
        UniqueConstraint("teacher_id", "fingerprint", name="uk_teaching_risks_teacher_fingerprint"),
        Index("idx_teaching_risks_queue", "teacher_id", "status", "severity", "detected_at"),
    )

    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"))
    student_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"))
    assignment_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("assignments.id", ondelete="CASCADE", onupdate="CASCADE"))
    question_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="SET NULL", onupdate="CASCADE"))
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(ENUM("low", "medium", "high"), nullable=False, server_default=text("'medium'"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(191), nullable=False)
    status: Mapped[str] = mapped_column(ENUM("open", "acknowledged", "resolved"), nullable=False, server_default=text("'open'"))
    detected_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME)


class TeachingArtifact(IdMixin, TimestampMixin, Base):
    __tablename__ = "teaching_artifacts"
    __table_args__ = (Index("idx_teaching_artifacts_scope", "teacher_id", "artifact_type", "class_id", "status"),)

    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    class_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"))
    student_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"))
    assignment_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("assignments.id", ondelete="CASCADE", onupdate="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(ENUM("draft", "confirmed", "archived"), nullable=False, server_default=text("'draft'"))


class AIPregrade(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_pregrades"
    __table_args__ = (UniqueConstraint("record_id", name="uk_ai_pregrades_record"),)

    record_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("practice_records.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    suggested_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    issues_json: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(ENUM("draft", "accepted", "rejected"), nullable=False, server_default=text("'draft'"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME)


class StudentHelpSignal(IdMixin, TimestampMixin, Base):
    __tablename__ = "student_help_signals"
    __table_args__ = (
        UniqueConstraint("teacher_id", "fingerprint", name="uk_student_help_signals_fingerprint"),
        Index("idx_student_help_signals_queue", "teacher_id", "status", "created_at"),
    )

    student_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("classes.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    question_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="SET NULL", onupdate="CASCADE"))
    knowledge_tag: Mapped[str | None] = mapped_column(String(160))
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(191), nullable=False)
    status: Mapped[str] = mapped_column(ENUM("open", "contacted", "resolved"), nullable=False, server_default=text("'open'"))
