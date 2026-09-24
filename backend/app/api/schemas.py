from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatContext(BaseModel):
    type: Literal["question", "wrong", "solution_step", "plan", "assignment", "diagnosis", "class", "student", "review"]
    question_id: int | None = Field(default=None, ge=1)
    record_id: int | None = Field(default=None, ge=1)
    assignment_id: int | None = Field(default=None, ge=1)
    class_id: int | None = Field(default=None, ge=1)
    student_id: int | None = Field(default=None, ge=1)
    step_no: int | None = Field(default=None, ge=1, le=30)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    session_id: str | None = Field(default=None, max_length=64)
    context: ChatContext | None = None

class GoalRequest(BaseModel):
    target_course: str = Field(default="高等数学上", min_length=1, max_length=128)
    target_stage: str = Field(default="大一", min_length=1, max_length=16)
    weekly_hours: float = Field(default=8.0, ge=0.5, le=80)
    exam_date: date | None = None


class UserCoursesRequest(BaseModel):
    courses: list[str] = Field(min_length=1, max_length=20)
    primary_course: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_courses(self) -> "UserCoursesRequest":
        self.courses = list(dict.fromkeys(item.strip() for item in self.courses if item.strip()))
        if not self.courses:
            raise ValueError("请至少选择一门课程。")
        if self.primary_course and self.primary_course not in self.courses:
            raise ValueError("主课程必须包含在所选课程中。")
        return self

class NoteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(default="", max_length=6000)
    course: str | None = Field(default=None, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)

class NoteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=6000)
    course: str | None = Field(default=None, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    attachment_ids: list[int] | None = Field(default=None, max_length=10)

class AnswerSubmissionRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    question_id: int = Field(ge=1)
    selected_answer: str | None = Field(default=None, max_length=16)
    answer_text: str | None = Field(default=None, max_length=6000)
    answer_steps: list[str] = Field(default_factory=list, max_length=20)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    time_spent_seconds: int = Field(default=0, ge=0)
    practice_mode: str = Field(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom|assessment)$")


class AISimilarPracticeRequest(BaseModel):
    question_id: int | None = Field(default=None, ge=1)
    course: str | None = Field(default=None, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    question_type: str | None = Field(default=None, pattern="^(choice|blank|calculation|proof|comprehensive)$")
    count: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def validate_source(self) -> "AISimilarPracticeRequest":
        if not self.question_id and not (self.course or self.knowledge_tag):
            raise ValueError("请选择原题，或提供课程/知识点。")
        return self


class AISelfCheckResultRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    source_question_id: int = Field(ge=1)
    generated_question: str = Field(min_length=2, max_length=12000)
    selected_answer: str | None = Field(default=None, max_length=1000)
    answer_text: str | None = Field(default=None, max_length=6000)
    expected_answer: str = Field(min_length=1, max_length=12000)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    evidence_type: Literal["selfcheck", "transfer"] = "selfcheck"
    time_spent_seconds: int = Field(default=0, ge=0, le=7200)

    @model_validator(mode="after")
    def validate_answer(self) -> "AISelfCheckResultRequest":
        if not (self.selected_answer or "").strip() and not (self.answer_text or "").strip():
            raise ValueError("请先完成自测答案。")
        return self


class ChainRecoveryRequest(BaseModel):
    record_id: int = Field(ge=1)


class QuestionCommentRequest(BaseModel):
    content: str | None = Field(default=None, max_length=3000)
    image_ids: list[int] = Field(default_factory=list, max_length=5)
    parent_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_body(self) -> "QuestionCommentRequest":
        self.content = (self.content or "").strip() or None
        if not self.content and not self.image_ids:
            raise ValueError("评论文字或图片至少需要提供一种。")
        if len(set(self.image_ids)) != len(self.image_ids):
            raise ValueError("评论图片不能重复。")
        return self


class NotificationPreferenceRequest(BaseModel):
    notify_xiaoluo: bool = True


class TicketReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class AssessmentStartRequest(BaseModel):
    stage: str | None = Field(default=None, max_length=16)
    limit: int = Field(default=12, ge=5, le=30)
    restart: bool = False


class QuestionRefRequest(BaseModel):
    question_id: int = Field(ge=1)
    record_id: int | None = Field(default=None, ge=1)


class MessageStartRequest(BaseModel):
    target_user_id: int = Field(ge=1)
    relation: Literal["teacher_student", "student_student"]


class MessageSendRequest(BaseModel):
    content: str | None = Field(default=None, max_length=5000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    question_ref: QuestionRefRequest | None = None
    message_type: Literal["chat", "advice"] = "chat"

    @model_validator(mode="after")
    def validate_content(self) -> "MessageSendRequest":
        self.content = (self.content or "").strip() or None
        if len(set(self.attachment_ids)) != len(self.attachment_ids):
            raise ValueError("消息图片不能重复。")
        if not self.content and not self.attachment_ids and not self.question_ref:
            raise ValueError("文本、图片或题目引用至少需要提供一种。")
        return self
