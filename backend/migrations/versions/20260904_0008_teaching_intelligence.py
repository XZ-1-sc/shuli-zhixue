"""teaching intelligence: structured solutions, paper workflow and teacher memory

Revision ID: 20260904_0008
Revises: 20260903_0007
Create Date: 2026-09-04

All changes are additive.  AI output is stored as a draft/evidence layer and
never bypasses the existing publish or teacher-review workflows.
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260904_0008"
down_revision: str | Sequence[str] | None = "20260903_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector | None, table: str, column: str) -> bool:
    return bool(inspector and inspector.has_table(table) and column in {item["name"] for item in inspector.get_columns(table)})


def upgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())

    additions = {
        "questions": [
            ("solution_steps", sa.JSON(), True, None),
            ("steps_source", mysql.ENUM("legacy", "ai", "teacher"), False, sa.text("'legacy'")),
            ("steps_review_status", mysql.ENUM("not_required", "pending", "verified", "needs_review"), False, sa.text("'not_required'")),
        ],
        "practice_records": [
            ("step_feedback", sa.JSON(), True, None),
            ("mastery_evidence", mysql.ENUM("formal", "selfcheck", "transfer"), False, sa.text("'formal'")),
            ("ai_evidence_json", sa.JSON(), True, None),
        ],
        "assignments": [
            ("ai_intent_json", sa.JSON(), True, None),
            ("review_report_json", sa.JSON(), True, None),
            ("lecture_draft", mysql.LONGTEXT(), True, None),
            ("teacher_adjustments_json", sa.JSON(), True, None),
            ("ai_generated", mysql.TINYINT(display_width=1), False, sa.text("0")),
        ],
    }
    for table, columns in additions.items():
        for name, column_type, nullable, default in columns:
            if offline or not _has_column(inspector, table, name):
                op.add_column(table, sa.Column(name, column_type, nullable=nullable, server_default=default))

    op.alter_column(
        "practice_records",
        "practice_mode",
        existing_type=mysql.ENUM("daily", "chapter", "mock", "wrong_book", "custom", "assessment", "assignment"),
        type_=mysql.ENUM("daily", "chapter", "mock", "wrong_book", "custom", "assessment", "assignment", "ai_similar"),
        existing_nullable=False,
        existing_server_default=sa.text("'custom'"),
    )

    if offline or not inspector.has_table("teacher_experiences"):
        op.create_table(
            "teacher_experiences",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("knowledge_tag", sa.String(160), nullable=True),
            sa.Column("experience_text", sa.Text(), nullable=False),
            sa.Column("status", mysql.ENUM("active", "archived"), nullable=False, server_default=sa.text("'active'")),
            sa.Column("usage_count", mysql.INTEGER(unsigned=True), nullable=False, server_default=sa.text("0")),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"], onupdate="CASCADE", ondelete="SET NULL"),
        )
        op.create_index("idx_teacher_experiences_lookup", "teacher_experiences", ["teacher_id", "knowledge_tag", "status"])

    if offline or not inspector.has_table("teacher_ai_preferences"):
        op.create_table(
            "teacher_ai_preferences",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("tone", sa.String(64), nullable=False, server_default=sa.text("'清晰、鼓励、重方法'")),
            sa.Column("scoring_strictness", mysql.ENUM("lenient", "balanced", "strict"), nullable=False, server_default=sa.text("'balanced'")),
            sa.Column("preferred_types", sa.JSON(), nullable=True),
            sa.Column("style_notes", sa.Text(), nullable=True),
            sa.Column("assistant_enabled", mysql.TINYINT(display_width=1), nullable=False, server_default=sa.text("1")),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.UniqueConstraint("teacher_id", name="uk_teacher_ai_preferences_teacher"),
        )

    if offline or not inspector.has_table("teaching_risks"):
        op.create_table(
            "teaching_risks",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("student_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("assignment_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("risk_type", sa.String(64), nullable=False),
            sa.Column("severity", mysql.ENUM("low", "medium", "high"), nullable=False, server_default=sa.text("'medium'")),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("fingerprint", sa.String(191), nullable=False),
            sa.Column("status", mysql.ENUM("open", "acknowledged", "resolved"), nullable=False, server_default=sa.text("'open'")),
            sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"], onupdate="CASCADE", ondelete="SET NULL"),
            sa.UniqueConstraint("teacher_id", "fingerprint", name="uk_teaching_risks_teacher_fingerprint"),
        )
        op.create_index("idx_teaching_risks_queue", "teaching_risks", ["teacher_id", "status", "severity", "detected_at"])

    if offline or not inspector.has_table("teaching_artifacts"):
        op.create_table(
            "teaching_artifacts",
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("artifact_type", sa.String(64), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("student_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("assignment_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content_json", sa.JSON(), nullable=False),
            sa.Column("source_snapshot_json", sa.JSON(), nullable=True),
            sa.Column("status", mysql.ENUM("draft", "confirmed", "archived"), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], onupdate="CASCADE", ondelete="CASCADE"),
        )
        op.create_index("idx_teaching_artifacts_scope", "teaching_artifacts", ["teacher_id", "artifact_type", "class_id", "status"])

    if offline or not inspector.has_table("ai_pregrades"):
        op.create_table(
            "ai_pregrades",
            sa.Column("record_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("suggested_score", sa.DECIMAL(5, 2), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("issues_json", sa.JSON(), nullable=True),
            sa.Column("status", mysql.ENUM("draft", "accepted", "rejected"), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["record_id"], ["practice_records.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.UniqueConstraint("record_id", name="uk_ai_pregrades_record"),
        )

    if offline or not inspector.has_table("student_help_signals"):
        op.create_table(
            "student_help_signals",
            sa.Column("student_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("teacher_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("class_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("knowledge_tag", sa.String(160), nullable=True),
            sa.Column("signal_type", sa.String(64), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("fingerprint", sa.String(191), nullable=False),
            sa.Column("status", mysql.ENUM("open", "contacted", "resolved"), nullable=False, server_default=sa.text("'open'")),
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"], onupdate="CASCADE", ondelete="SET NULL"),
            sa.UniqueConstraint("teacher_id", "fingerprint", name="uk_student_help_signals_fingerprint"),
        )
        op.create_index("idx_student_help_signals_queue", "student_help_signals", ["teacher_id", "status", "created_at"])


def downgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    for table in ("student_help_signals", "ai_pregrades", "teaching_artifacts", "teaching_risks", "teacher_ai_preferences", "teacher_experiences"):
        if offline or inspector.has_table(table):
            op.drop_table(table)
    if not offline:
        op.get_bind().execute(sa.text("UPDATE practice_records SET practice_mode='custom' WHERE practice_mode='ai_similar'"))
    op.alter_column(
        "practice_records",
        "practice_mode",
        existing_type=mysql.ENUM("daily", "chapter", "mock", "wrong_book", "custom", "assessment", "assignment", "ai_similar"),
        type_=mysql.ENUM("daily", "chapter", "mock", "wrong_book", "custom", "assessment", "assignment"),
        existing_nullable=False,
        existing_server_default=sa.text("'custom'"),
    )
    for table, columns in {
        "assignments": ("ai_generated", "teacher_adjustments_json", "lecture_draft", "review_report_json", "ai_intent_json"),
        "practice_records": ("ai_evidence_json", "mastery_evidence", "step_feedback"),
        "questions": ("steps_review_status", "steps_source", "solution_steps"),
    }.items():
        inspector = None if offline else sa.inspect(op.get_bind())
        for column in columns:
            if offline or _has_column(inspector, table, column):
                op.drop_column(table, column)
