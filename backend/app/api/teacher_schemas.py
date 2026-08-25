from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


QUESTION_TYPES = {"choice", "blank", "calculation", "proof", "comprehensive"}
TYPE_LABELS = {
    "choice": "选择题",
    "blank": "填空题",
    "calculation": "计算题",
    "proof": "证明题",
    "comprehensive": "综合题",
}


class QuestionWriteRequest(BaseModel):
    question_type: Literal["choice", "blank", "calculation", "proof", "comprehensive"]
    stage: str = Field(min_length=2, max_length=16)
    course: str = Field(min_length=1, max_length=128)
    knowledge_tag: str = Field(min_length=1, max_length=160)
    fine_tag: str = Field(min_length=1, max_length=160)
    difficulty: int = Field(default=3, ge=1, le=5)
    question_text: str = Field(min_length=2, max_length=12000)
    option_a: str | None = Field(default=None, max_length=4000)
    option_b: str | None = Field(default=None, max_length=4000)
    option_c: str | None = Field(default=None, max_length=4000)
    option_d: str | None = Field(default=None, max_length=4000)
    correct_answer: str | None = Field(default=None, max_length=16)
    standard_answer: str = Field(min_length=1, max_length=12000)
    analysis_text: str = Field(min_length=1, max_length=20000)
    key_steps: list[str] = Field(default_factory=list, max_length=20)
    common_errors: list[str] = Field(default_factory=list, max_length=20)
    mistake_tags: list[str] = Field(default_factory=list, max_length=20)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    analysis_attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    visibility: Literal["public", "class"] = "public"
    publish_status: Literal["draft", "published"] = "draft"

    @model_validator(mode="after")
    def validate_choice(self) -> "QuestionWriteRequest":
        if self.question_type == "choice":
            if not all([self.option_a, self.option_b, self.option_c, self.option_d]):
                raise ValueError("选择题必须填写 A、B、C、D 四个选项。")
            if (self.correct_answer or "").strip().upper() not in {"A", "B", "C", "D"}:
                raise ValueError("选择题正确答案必须是 A、B、C 或 D。")
        return self

class AssignmentWriteRequest(BaseModel):
    class_id: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    question_ids: list[int] = Field(min_length=1, max_length=100)
    points: list[float] | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None
    time_limit_minutes: int | None = Field(default=None, ge=5, le=600)
    max_attempts: int = Field(default=1, ge=1, le=5)
    show_analysis_after_submit: bool = True
    publish: bool = False

    @model_validator(mode="after")
    def validate_assignment(self) -> "AssignmentWriteRequest":
        if len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError("作业题目不能重复。")
        if self.points is not None and len(self.points) != len(self.question_ids):
            raise ValueError("题目分值数量必须和题目数量一致。")
        if self.due_at and self.starts_at and self.due_at <= self.starts_at:
            raise ValueError("截止时间必须晚于开始时间。")
        return self

class QuestionImportCommitRequest(BaseModel):
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    publish_status: Literal["draft", "published"] = "draft"
    visibility: Literal["public", "class"] = "public"
    source_file_name: str = Field(default="导入文件", max_length=255)
    skip_duplicates: bool = True
    reuse_duplicates: bool = False

class ReviewRequest(BaseModel):
    score: float = Field(ge=0, le=100)
    feedback: str = Field(min_length=1, max_length=4000)
    correction_required: bool = False


class GradeCommentAIRequest(BaseModel):
    record_id: int | None = Field(default=None, ge=1)
    record_ids: list[int] | None = Field(default=None, min_length=1, max_length=20)
    draft_score: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_record_scope(self) -> "GradeCommentAIRequest":
        if bool(self.record_id) == bool(self.record_ids):
            raise ValueError("单条 record_id 与批量 record_ids 必须且只能提供一种。")
        if self.record_ids and len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError("批量作答编号不能重复。")
        return self


class ClassInsightAIRequest(BaseModel):
    scope: Literal["class", "student"]
    class_id: int | None = Field(default=None, ge=1)
    student_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_scope_id(self) -> "ClassInsightAIRequest":
        if self.scope == "class" and not self.class_id:
            raise ValueError("班级学情解读必须提供 class_id。")
        if self.scope == "student" and not self.student_id:
            raise ValueError("学生学情解读必须提供 student_id。")
        return self


class AssignmentSuggestionAIRequest(BaseModel):
    class_id: int = Field(ge=1)
    question_count: int = Field(default=10, ge=1, le=100)


class AssignmentReportAIRequest(BaseModel):
    assignment_id: int = Field(ge=1)
