from datetime import datetime

from sqlalchemy import CHAR, DATETIME, ForeignKey, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, ENUM, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uk_users_username"),
        UniqueConstraint("email", name="uk_users_email"),
        Index("idx_users_role_status", "role", "status"),
    )

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(
        ENUM("student", "teacher", "admin"), nullable=False, server_default=text("'student'")
    )
    current_stage: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'大一'"))
    status: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("1"))
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME)


class TeacherProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "teacher_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uk_teacher_profiles_user"),)

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(160))
    verification_status: Mapped[str] = mapped_column(
        ENUM("verified", "disabled"), nullable=False, server_default=text("'verified'")
    )


class AuthSession(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uk_auth_sessions_token"),
        Index("idx_auth_sessions_user_active", "user_id", "revoked_at", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64, collation="ascii_bin"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DATETIME, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME)


class AuditLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_actor_time", "actor_user_id", "created_at"),
        Index("idx_audit_logs_entity", "entity_type", "entity_id"),
    )

    actor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    payload: Mapped[dict | None] = mapped_column(JSON)


class TeacherInviteCode(IdMixin, TimestampMixin, Base):
    __tablename__ = "teacher_invite_codes"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uk_teacher_invite_codes_hash"),
        Index("idx_teacher_invite_codes_active", "status", "expires_at"),
    )

    code_hash: Mapped[str] = mapped_column(CHAR(64, collation="ascii_bin"), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        ENUM("active", "revoked"), nullable=False, server_default=text("'active'")
    )
    max_uses: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)
    used_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DATETIME)
    last_used_at: Mapped[datetime | None] = mapped_column(DATETIME)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE")
    )
