import unittest

from pydantic import ValidationError

from datetime import date

from backend.app.api.schemas import AISimilarPracticeRequest, ChatContext, ChatRequest, NotificationPreferenceRequest
from backend.app.api.teacher_schemas import ClassInsightAIRequest, GradeCommentAIRequest
from backend.app.services.reminder_service import _parse_plan_due


class AIContractTests(unittest.TestCase):
    def test_chat_context_accepts_owned_resource_identifiers_only_as_ids(self) -> None:
        request = ChatRequest(
            message="这题为什么错？",
            context=ChatContext(type="question", question_id=12, record_id=34),
        )
        self.assertEqual(request.context.record_id, 34)
        with self.assertRaises(ValidationError):
            ChatContext(type="question", question_id=0)

    def test_teacher_insight_requires_scope_identifier(self) -> None:
        with self.assertRaises(ValidationError):
            ClassInsightAIRequest(scope="class")
        payload = ClassInsightAIRequest(scope="student", student_id=9)
        self.assertEqual(payload.student_id, 9)

    def test_similar_practice_count_is_bounded(self) -> None:
        payload = AISimilarPracticeRequest(question_id=12, count=2)
        self.assertEqual(payload.count, 2)
        with self.assertRaises(ValidationError):
            AISimilarPracticeRequest(question_id=12, count=3)

    def test_grade_comment_batch_scope_is_exclusive_and_unique(self) -> None:
        payload = GradeCommentAIRequest(record_ids=[3, 4])
        self.assertEqual(payload.record_ids, [3, 4])
        with self.assertRaises(ValidationError):
            GradeCommentAIRequest(record_id=3, record_ids=[4])
        with self.assertRaises(ValidationError):
            GradeCommentAIRequest(record_ids=[3, 3])

    def test_notification_preference_and_plan_due_contracts(self) -> None:
        self.assertFalse(NotificationPreferenceRequest(notify_xiaoluo=False).notify_xiaoluo)
        plan = {"tasks": [{"title": "复盘导数错题", "due_date": "2026-08-23", "completed": False}]}
        self.assertEqual(_parse_plan_due(plan, date(2026, 8, 23)), "复盘导数错题")
        plan["tasks"][0]["completed"] = True
        self.assertIsNone(_parse_plan_due(plan, date(2026, 8, 23)))


if __name__ == "__main__":
    unittest.main()
