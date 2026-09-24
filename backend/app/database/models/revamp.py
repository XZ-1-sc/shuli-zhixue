from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class UserCourse(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_courses"
    __table_args__ = (
        UniqueConstraint("user_id", "course_name", name="uk_user_courses_user_course"),
        Index("idx_user_courses_order", "user_id", "is_primary", "course_order"),
    )

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    course_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_primary: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))
    course_order: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False, server_default=text("0"))


class CourseRelation(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "course_relations"
    __table_args__ = (
        UniqueConstraint("from_course", "to_course", "relation", name="uk_course_relations_pair"),
        Index("idx_course_relations_from", "from_course", "relation"),
        Index("idx_course_relations_to", "to_course", "relation"),
    )

    from_course: Mapped[str] = mapped_column(String(128), nullable=False)
    to_course: Mapped[str] = mapped_column(String(128), nullable=False)
    relation: Mapped[str] = mapped_column(ENUM("prerequisite", "related"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))


class UserAIProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_ai_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uk_user_ai_profiles_user"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    diagnosis_json: Mapped[dict | None] = mapped_column(JSON)
    previous_diagnosis_json: Mapped[dict | None] = mapped_column(JSON)
    trend_json: Mapped[dict | None] = mapped_column(JSON)
    advice_json: Mapped[dict | None] = mapped_column(JSON)
    last_diagnosed_at: Mapped[datetime | None] = mapped_column(DateTime)


class QuestionComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "question_comments"
    __table_args__ = (
        Index("idx_question_comments_question", "question_id", "status", "is_best", "created_at"),
        Index("idx_question_comments_user", "user_id", "created_at"),
    )

    question_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("question_comments.id", ondelete="SET NULL", onupdate="CASCADE"))
    content: Mapped[str | None] = mapped_column(Text)
    image_ids: Mapped[list | None] = mapped_column(JSON)
    upvotes: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    is_best: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(ENUM("active", "hidden"), nullable=False, server_default=text("'active'"))


class CommentUpvote(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "comment_upvotes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uk_comment_upvotes_comment_user"),)

    comment_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("question_comments.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
