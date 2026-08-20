from datetime import date

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    session_id: str | None = Field(default=None, max_length=64)

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

class AssessmentStartRequest(BaseModel):
    stage: str | None = Field(default=None, max_length=16)
    limit: int = Field(default=12, ge=5, le=30)
    restart: bool = False

