from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatContext(BaseModel):
    type: Literal["question", "wrong", "plan", "assignment", "diagnosis", "class", "student", "review"]
    question_id: int | None = Field(default=None, ge=1)
    record_id: int | None = Field(default=None, ge=1)
    assignment_id: int | None = Field(default=None, ge=1)
    class_id: int | None = Field(default=None, ge=1)
    student_id: int | None = Field(default=None, ge=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    session_id: str | None = Field(default=None, max_length=64)
    context: ChatContext | None = None

class GoalRequest(BaseModel):
    target_course: str = Field(default="高等数学上", min_length=1, max_length=128)
    target_stage: str = Field(default="大一", min_length=1, max_length=16)
    weekly_hours: float = Field(default=8.0, ge=0.5, le=80)
    exam_date: date | None = None

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
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    time_spent_seconds: int = Field(default=0, ge=0)
    practice_mode: str = Field(default="custom", pattern="^(daily|chapter|mock|wrong_book|custom|assessment)$")


class AISimilarPracticeRequest(BaseModel):
    question_id: int = Field(ge=1)
    count: int = Field(default=2, ge=1, le=2)


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
