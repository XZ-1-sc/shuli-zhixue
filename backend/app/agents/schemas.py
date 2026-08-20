from typing import Literal

from pydantic import BaseModel, Field


ReasonType = Literal["概念混淆", "计算失误", "证明思路断点", "知识点不会", "做题慢"]


class WeakPoint(BaseModel):
    stage: str = Field(min_length=1, max_length=16)
    course: str = Field(min_length=1, max_length=128)
    knowledge: str = Field(min_length=1, max_length=160)
    reason_type: ReasonType
    suggestion: str = Field(min_length=1, max_length=500)


class Diagnosis(BaseModel):
    weak_points: list[WeakPoint] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)
    needs_first_test: bool = False


class WeeklyPlan(BaseModel):
    focus_course: str = Field(min_length=1, max_length=128)
    focus_knowledge: str = Field(min_length=1, max_length=160)
    daily_hours: float = Field(ge=0.25, le=12)
    priority_order: list[str] = Field(default_factory=list, max_length=10)
    give_up_types: list[str] = Field(default_factory=list, max_length=10)


class ClarityReview(BaseModel):
    clear: bool
    missing: list[str] = Field(default_factory=list, max_length=10)
    feedback: str = Field(default="", max_length=1000)


class RecommendationQuery(BaseModel):
    course: str = Field(min_length=1, max_length=128)
    knowledge_tag: str | None = Field(default=None, max_length=160)
    difficulty: int = Field(default=3, ge=1, le=5)


class EvaluationResult(BaseModel):
    accuracy: float = Field(ge=0, le=1)
    delta: float
    trend: Literal["first_record", "improving", "declining", "stable"]
    current_total: int = Field(ge=0)
    summary: str


class LLMUsage(BaseModel):
    model: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    status: str = "success"
    error_message: str | None = None
