from datetime import datetime

from sqlalchemy import CheckConstraint, DATETIME, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, LONGTEXT, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class SourceAttribution(IdMixin, Base):
    __tablename__ = "source_attributions"
    __table_args__ = (UniqueConstraint("source_name", name="uk_source_attributions_name"),)

    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    license_name: Mapped[str] = mapped_column(String(160), nullable=False)
    license_url: Mapped[str] = mapped_column(String(512), nullable=False)
    usage_note: Mapped[str | None] = mapped_column(Text)
    downloaded_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class MathStage(IdMixin, Base):
    __tablename__ = "math_stages"
    __table_args__ = (
        UniqueConstraint("stage_name", name="uk_math_stages_name"),
        UniqueConstraint("stage_order", name="uk_math_stages_order"),
    )

    stage_name: Mapped[str] = mapped_column(String(16), nullable=False)
    stage_order: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)


class MathCourse(IdMixin, Base):
    __tablename__ = "math_courses"
    __table_args__ = (
        UniqueConstraint("stage_id", "course_name", name="uk_math_courses_stage_course"),
        Index("idx_math_courses_group", "course_group"),
    )

    stage_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("math_stages.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    course_name: Mapped[str] = mapped_column(String(128), nullable=False)
    course_group: Mapped[str] = mapped_column(String(64), nullable=False)
    course_order: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(Text)


class KnowledgeNode(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        UniqueConstraint("node_code", name="uk_knowledge_nodes_code"),
        Index("idx_knowledge_nodes_parent", "parent_id"),
        Index("idx_knowledge_nodes_stage_course", "stage_name", "course_name"),
        Index("idx_knowledge_nodes_name", "name"),
    )

    node_code: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("knowledge_nodes.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    stage_name: Mapped[str] = mapped_column(String(16), nullable=False)
    course_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    level: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    sort_order: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(Text)


class MistakeTag(IdMixin, Base):
    __tablename__ = "mistake_tags"
    __table_args__ = (UniqueConstraint("tag_name", name="uk_mistake_tags_name"),)

    tag_name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("source_id", "source_question_no", name="uk_questions_source_no"),
        Index("idx_questions_stage_course", "stage", "course"),
        Index("idx_questions_type", "question_type"),
        Index("idx_questions_knowledge", "knowledge_tag", "fine_tag"),
        Index("idx_questions_difficulty", "difficulty"),
        Index("idx_questions_knowledge_node", "knowledge_node_id"),
        Index("idx_questions_creator_status", "created_by", "publish_status", "deleted_at"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="chk_questions_difficulty"),
    )

    source_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("source_attributions.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    visibility: Mapped[str] = mapped_column(
        ENUM("public", "class"), nullable=False, server_default=text("'public'")
    )
    publish_status: Mapped[str] = mapped_column(
        ENUM("draft", "published", "archived"), nullable=False, server_default=text("'published'")
    )
    version: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("1"))
    published_at: Mapped[datetime | None] = mapped_column(DATETIME)
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME)
    source_question_no: Mapped[str] = mapped_column(String(128), nullable=False)
    source_path: Mapped[str] = mapped_column(String(768), nullable=False)
    question_type: Mapped[str] = mapped_column(
        ENUM("choice", "blank", "calculation", "proof", "comprehensive"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    course: Mapped[str] = mapped_column(String(128), nullable=False)
    knowledge_node_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("knowledge_nodes.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    knowledge_tag: Mapped[str] = mapped_column(String(160), nullable=False)
    fine_tag: Mapped[str] = mapped_column(String(160), nullable=False)
    difficulty: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("3"))
    question_text: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    option_a: Mapped[str | None] = mapped_column(Text)
    option_b: Mapped[str | None] = mapped_column(Text)
    option_c: Mapped[str | None] = mapped_column(Text)
    option_d: Mapped[str | None] = mapped_column(Text)
    correct_answer: Mapped[str | None] = mapped_column(String(16))
    standard_answer: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    analysis_text: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    key_steps: Mapped[list] = mapped_column(JSON, nullable=False)
    common_errors: Mapped[list] = mapped_column(JSON, nullable=False)
    mistake_tags: Mapped[list] = mapped_column(JSON, nullable=False)


class QuestionAttachment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "question_attachments"
    __table_args__ = (
        UniqueConstraint("uploaded_file_id", name="uk_question_attachments_file"),
        Index("idx_question_attachments_question", "question_id", "attachment_type", "sort_order"),
    )

    question_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    uploaded_file_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("uploaded_files.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    attachment_type: Mapped[str] = mapped_column(
        ENUM("question", "analysis"), nullable=False, server_default=text("'question'")
    )
    sort_order: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, server_default=text("1"))
