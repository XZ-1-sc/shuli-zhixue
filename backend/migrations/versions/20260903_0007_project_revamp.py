"""project revamp: course graph, AI profile and question discussions

Revision ID: 20260903_0007
Revises: 20260825_0006
Create Date: 2026-09-03

The migration is deliberately additive.  Historical stage columns remain in place
for old records and rollback compatibility; the application no longer exposes
them as the primary navigation model.
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260903_0007"
down_revision: str | Sequence[str] | None = "20260825_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector | None, table: str, column: str) -> bool:
    return bool(inspector and inspector.has_table(table) and column in {item["name"] for item in inspector.get_columns(table)})


def upgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())

    if offline or not inspector.has_table("user_courses"):
        op.create_table(
            "user_courses",
            sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("course_name", sa.String(128), nullable=False),
            sa.Column("is_primary", mysql.TINYINT(display_width=1), server_default=sa.text("0"), nullable=False),
            sa.Column("course_order", mysql.SMALLINT(unsigned=True), server_default=sa.text("0"), nullable=False),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "course_name", name="uk_user_courses_user_course"),
        )
        op.create_index("idx_user_courses_order", "user_courses", ["user_id", "is_primary", "course_order"])

    if offline or not inspector.has_table("course_relations"):
        op.create_table(
            "course_relations",
            sa.Column("from_course", sa.String(128), nullable=False),
            sa.Column("to_course", sa.String(128), nullable=False),
            sa.Column("relation", mysql.ENUM("prerequisite", "related"), nullable=False),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("from_course", "to_course", "relation", name="uk_course_relations_pair"),
        )
        op.create_index("idx_course_relations_from", "course_relations", ["from_course", "relation"])
        op.create_index("idx_course_relations_to", "course_relations", ["to_course", "relation"])

    if offline or not inspector.has_table("user_ai_profiles"):
        op.create_table(
            "user_ai_profiles",
            sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("diagnosis_json", sa.JSON(), nullable=True),
            sa.Column("previous_diagnosis_json", sa.JSON(), nullable=True),
            sa.Column("trend_json", sa.JSON(), nullable=True),
            sa.Column("advice_json", sa.JSON(), nullable=True),
            sa.Column("last_diagnosed_at", sa.DateTime(), nullable=True),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uk_user_ai_profiles_user"),
        )

    if offline or not inspector.has_table("question_comments"):
        op.create_table(
            "question_comments",
            sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("parent_id", mysql.BIGINT(unsigned=True), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("image_ids", sa.JSON(), nullable=True),
            sa.Column("upvotes", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
            sa.Column("is_best", mysql.TINYINT(display_width=1), server_default=sa.text("0"), nullable=False),
            sa.Column("status", mysql.ENUM("active", "hidden"), server_default="active", nullable=False),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["question_comments.id"], onupdate="CASCADE", ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_question_comments_question", "question_comments", ["question_id", "status", "is_best", "created_at"])
        op.create_index("idx_question_comments_user", "question_comments", ["user_id", "created_at"])

    if offline or not inspector.has_table("comment_upvotes"):
        op.create_table(
            "comment_upvotes",
            sa.Column("comment_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
            sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["comment_id"], ["question_comments.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comment_id", "user_id", name="uk_comment_upvotes_comment_user"),
        )

    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or not _has_column(inspector, "questions", "ai_generated"):
        op.add_column("questions", sa.Column("ai_generated", mysql.TINYINT(display_width=1), server_default=sa.text("0"), nullable=False))
    if offline or not _has_column(inspector, "questions", "source_question_id"):
        op.add_column("questions", sa.Column("source_question_id", mysql.BIGINT(unsigned=True), nullable=True))
        op.create_index("idx_questions_source_question", "questions", ["source_question_id"])
        op.create_foreign_key("fk_questions_source_question", "questions", "questions", ["source_question_id"], ["id"], onupdate="CASCADE", ondelete="SET NULL")
    if offline or not _has_column(inspector, "practice_records", "answer_steps"):
        op.add_column("practice_records", sa.Column("answer_steps", sa.JSON(), nullable=True))

    if not offline:
        connection = op.get_bind()
        connection.execute(sa.text("""
            INSERT INTO user_courses (user_id,course_name,is_primary,course_order)
            SELECT user_id,target_course,1,0 FROM user_goal_settings
            WHERE target_course IS NOT NULL AND target_course <> ''
            ON DUPLICATE KEY UPDATE is_primary=VALUES(is_primary)
        """))
        connection.execute(sa.text("""
            INSERT INTO course_relations (from_course,to_course,relation,note) VALUES
            ('高等数学上','高等数学下','prerequisite','极限、导数与积分是后续内容的基础'),
            ('高等数学上','线性代数','related','函数与方程思想相互支撑'),
            ('高等数学下','概率论与数理统计','related','多元函数与积分支持概率建模'),
            ('线性代数','概率论与数理统计','related','矩阵方法用于多变量统计')
            ON DUPLICATE KEY UPDATE note=VALUES(note)
        """))


def downgrade() -> None:
    offline = op.get_context().as_sql
    inspector = None if offline else sa.inspect(op.get_bind())
    if offline or _has_column(inspector, "practice_records", "answer_steps"):
        op.drop_column("practice_records", "answer_steps")
    if offline or _has_column(inspector, "questions", "source_question_id"):
        if offline:
            op.drop_constraint("fk_questions_source_question", "questions", type_="foreignkey")
            op.drop_index("idx_questions_source_question", table_name="questions")
        else:
            for foreign_key in inspector.get_foreign_keys("questions"):
                if foreign_key.get("constrained_columns") == ["source_question_id"] and foreign_key.get("name"):
                    op.drop_constraint(str(foreign_key["name"]), "questions", type_="foreignkey")
            index_names = {item["name"] for item in inspector.get_indexes("questions")}
            if "idx_questions_source_question" in index_names:
                op.drop_index("idx_questions_source_question", table_name="questions")
        op.drop_column("questions", "source_question_id")
    if offline or _has_column(inspector, "questions", "ai_generated"):
        op.drop_column("questions", "ai_generated")
    for table in ("comment_upvotes", "question_comments", "user_ai_profiles", "course_relations", "user_courses"):
        inspector = None if offline else sa.inspect(op.get_bind())
        if offline or inspector.has_table(table):
            op.drop_table(table)
