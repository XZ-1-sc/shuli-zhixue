"""Portable AI-generation regression with a disposable in-memory SQL database.

No model calls, production credentials, migrations or business data are required.
Run: python -m unittest backend.tests.test_teacher_question_generator -v
"""
import json
import os
import random
import sqlite3
import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import security
from backend.app.agents.schemas import LLMUsage
from backend.app.api.routes import teacher_ai
from backend.app.api.teacher_schemas import QuestionWriteRequest, TeacherQuestionAIRequest
from backend.app.database.repositories import questions, teacher_questions
from backend.app.services import teacher_question_generator as generator


SCHEMA = [
    """CREATE TABLE math_stages (id INTEGER PRIMARY KEY, stage_name TEXT, stage_order INTEGER)""",
    """CREATE TABLE math_courses (id INTEGER PRIMARY KEY, stage_id INTEGER, course_name TEXT)""",
    """CREATE TABLE knowledge_nodes (id INTEGER PRIMARY KEY, stage_name TEXT, course_name TEXT, name TEXT, level INTEGER)""",
    """CREATE TABLE source_attributions (id INTEGER PRIMARY KEY, source_name TEXT, source_url TEXT,
        license_name TEXT, license_url TEXT, usage_note TEXT)""",
    """CREATE TABLE questions (
        id INTEGER PRIMARY KEY, source_id INTEGER, created_by INTEGER, visibility TEXT,
        publish_status TEXT, version INTEGER DEFAULT 1, published_at TIMESTAMP, deleted_at TIMESTAMP,
        source_question_no TEXT, source_path TEXT, question_type TEXT, stage TEXT, course TEXT,
        knowledge_node_id INTEGER, knowledge_tag TEXT, fine_tag TEXT, difficulty INTEGER,
        question_text TEXT, option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT,
        correct_answer TEXT, standard_answer TEXT, analysis_text TEXT, key_steps TEXT,
        common_errors TEXT, mistake_tags TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)""",
    """CREATE TABLE question_attachments (id INTEGER PRIMARY KEY, question_id INTEGER,
        uploaded_file_id INTEGER, attachment_type TEXT, sort_order INTEGER)""",
    """CREATE TABLE uploaded_files (id INTEGER PRIMARY KEY, original_name TEXT, mime_type TEXT, size_bytes INTEGER)""",
    """CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, actor_user_id INTEGER, action TEXT,
        entity_type TEXT, entity_id INTEGER, payload TEXT)""",
]


class JsonArrayAgg:
    def __init__(self):
        self.items = []

    def step(self, value):
        self.items.append(value)

    def finalize(self):
        return json.dumps(self.items)


def item(number=1, **overrides):
    return {
        "question_text": f"计算极限：当 x 趋向 {number} 时，x + 1 的极限。",
        "options": {"A": str(number + 1), "B": "0", "C": "-1", "D": "不存在"},
        "correct_answer": "A", "standard_answer": str(number + 1),
        "analysis_text": "连续函数的极限等于该点的函数值。",
        "key_steps": ["应用连续性"], "common_errors": [], **overrides,
    }


class TeacherQuestionGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:", poolclass=StaticPool,
            connect_args={"check_same_thread": False, "detect_types": sqlite3.PARSE_DECLTYPES},
        )

        @event.listens_for(self.engine, "connect")
        def functions(connection, _record):
            connection.create_function("RAND", 0, random.random)
            connection.create_function("NOW", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            connection.create_function("CONCAT", -1, lambda *args: "".join(map(str, args)))
            connection.create_aggregate("JSON_ARRAYAGG", 1, JsonArrayAgg)

        self.sessions = sessionmaker(bind=self.engine)
        with self.engine.begin() as db:
            for ddl in SCHEMA:
                db.execute(text(ddl))
            db.execute(text("INSERT INTO math_stages VALUES (1, '大一', 1)"))
            db.execute(text("INSERT INTO math_courses VALUES (1, 1, '高等数学上')"))
        self.stack = ExitStack()
        for module in [generator, teacher_questions, questions]:
            self.stack.enter_context(patch.object(module, "SessionLocal", self.sessions))
        self.llm = self.stack.enter_context(patch.object(generator, "call_llm_json"))
        self.llm.return_value = (
            generator.GeneratedTeacherQuestionSet(questions=[item()]), LLMUsage(model="test-model"),
        )
        app = FastAPI()
        app.include_router(teacher_ai.router)
        self.client = TestClient(app)
        self.payload = {"course": "高等数学上", "knowledge_tag": "函数与极限", "question_type": "choice", "count": 1}

    def tearDown(self):
        self.client.close()
        self.stack.close()
        self.engine.dispose()

    def generate(self, **values):
        return generator.generate_teacher_questions_sync(11, TeacherQuestionAIRequest(**(self.payload | values)))

    def query_count(self, table="questions"):
        with self.sessions() as db:
            return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

    def list_questions(self, teacher_id, scope="all"):
        return teacher_questions._questions_sync(teacher_id, scope, None, None, None, None, None, False, 1, 20)

    def test_five_types_keep_private_drafts_and_audit_without_ai_columns(self):
        for question_type in ["choice", "blank", "calculation", "proof", "comprehensive"]:
            with self.subTest(question_type=question_type):
                result = self.generate(question_type=question_type)
                self.assertEqual(result["created_count"], 1)
                saved = result["items"][0]
                self.assertEqual(saved["created_by"], 11)
                self.assertEqual(saved["publish_status"], "draft")
                self.assertEqual(saved["visibility"], "class")
                self.assertTrue(saved["ai_generated"])
                self.assertTrue(saved["source_path"].startswith("teacher-ai/11/"))
                self.assertIsNone(questions._get_question_sync(saved["id"]))
                with self.assertRaises(HTTPException):
                    teacher_questions._question_detail_sync(12, saved["id"])
        self.assertEqual(self.list_questions(11)["total"], 5)
        self.assertEqual(self.list_questions(12)["total"], 0)
        self.assertEqual(self.list_questions(11, "public")["total"], 0)
        self.assertEqual(questions._random_questions_sync(stage=None, course=None, knowledge_tag=None, question_type=None, limit=5), [])
        with self.sessions() as db:
            logs = db.execute(text("SELECT payload FROM audit_logs WHERE action='question.ai_generated'")).scalars().all()
        self.assertEqual(len(logs), 5)
        self.assertEqual(json.loads(logs[0])["model"], "test-model")

    def test_five_results_and_request_context(self):
        self.llm.return_value = (generator.GeneratedTeacherQuestionSet(questions=[item(i) for i in range(1, 6)]), LLMUsage(model="test"))
        result = self.generate(count=5, difficulty=4, requirements="参数为正整数")
        self.assertEqual(result["created_count"], 5)
        self.assertEqual(result["errors"], [])
        request = json.loads(self.llm.call_args.args[0][1]["content"])["request"]
        self.assertEqual(request["requirements"], "参数为正整数")
        self.assertEqual(request["difficulty"], 4)

    def test_partial_validation_and_duplicates(self):
        self.llm.return_value = (generator.GeneratedTeacherQuestionSet(questions=[
            item(), item(), item(2, options={"A": "1"}), item(3, analysis_text=" "), item(4),
        ]), LLMUsage(model="test"))
        result = self.generate(count=5)
        self.assertEqual(result["created_count"], 2)
        self.assertEqual([error["index"] for error in result["errors"]], [2, 3, 4])

    def test_empty_model_result_never_creates_placeholder(self):
        self.llm.return_value = (generator.GeneratedTeacherQuestionSet(), LLMUsage(model="test", status="fallback_unavailable"))
        result = self.generate(count=5)
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(len(result["errors"]), 5)
        self.assertEqual(self.query_count(), 0)

    def test_invalid_course_is_rejected_before_model_call(self):
        with self.assertRaises(HTTPException) as error:
            self.generate(course="不存在的课程")
        self.assertEqual(error.exception.status_code, 422)
        self.llm.assert_not_called()

    def test_request_bounds_and_whitespace(self):
        for invalid in [{"course": " "}, {"knowledge_tag": " "}, {"count": 0}, {"count": 6},
                        {"difficulty": 0}, {"difficulty": 6}, {"question_type": "essay"}, {"requirements": "x" * 1001}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                TeacherQuestionAIRequest(**(self.payload | invalid))

    def test_audit_failure_rolls_back_draft(self):
        audit = teacher_questions._audit

        def fail_ai_audit(db, actor, action, *args):
            if action == "question.ai_generated":
                raise SQLAlchemyError("simulated audit failure")
            return audit(db, actor, action, *args)

        with patch.object(teacher_questions, "_audit", side_effect=fail_ai_audit), self.assertLogs(generator.logger, level="ERROR"):
            result = self.generate()
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(self.query_count(), 0)
        self.assertEqual(self.query_count("audit_logs"), 0)

    def test_only_published_public_exemplars_are_used(self):
        self.generate()
        self.generate()
        context = json.loads(self.llm.call_args.args[0][1]["content"])
        self.assertIsNone(context["quality_reference"])

    def test_review_edit_and_explicit_publication_preserve_provenance(self):
        saved = self.generate()["items"][0]
        payload = QuestionWriteRequest(**{key: saved[key] for key in QuestionWriteRequest.model_fields if key in saved})
        payload.visibility = "public"
        payload.publish_status = "published"
        updated = teacher_questions._update_question_sync(11, saved["id"], payload)
        self.assertTrue(updated["ai_generated"])
        self.assertEqual(updated["publish_status"], "published")
        self.assertIsNotNone(questions._get_question_sync(saved["id"]))
        self.assertEqual(self.list_questions(12)["total"], 1)

    def test_private_creation_guard_and_manual_questions_unchanged(self):
        saved = self.generate()["items"][0]
        payload = QuestionWriteRequest(**{key: saved[key] for key in QuestionWriteRequest.model_fields if key in saved})
        payload.visibility = "public"
        with self.assertRaises(HTTPException):
            teacher_questions._create_question_sync(11, payload, ai_source={})
        manual = teacher_questions._create_question_sync(11, payload)
        self.assertFalse(manual["ai_generated"])
        self.assertTrue(manual["source_path"].startswith("teacher/11/"))

    def test_endpoint_authentication_and_validation(self):
        endpoint = "/api/teacher/ai/generate-question"
        self.assertEqual(self.client.post(endpoint, json=self.payload).status_code, 401)
        with patch.object(security, "current_session_user", return_value={"id": 12, "role": "student"}):
            self.assertEqual(self.client.post(endpoint, json=self.payload).status_code, 403)
        with patch.object(security, "current_session_user", return_value={"id": 11, "role": "teacher"}):
            self.assertEqual(self.client.post(endpoint, json=self.payload | {"count": 6}).status_code, 422)
            response = self.client.post(endpoint, json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["created_by"], 11)


if __name__ == "__main__":
    unittest.main()
