from .assessment import AnswerAttachment, AssessmentSession, AssessmentSessionQuestion, UploadedFile
from .base import Base
from .content import (
    KnowledgeNode,
    MathCourse,
    MathStage,
    MistakeTag,
    Question,
    QuestionAttachment,
    SourceAttribution,
)
from .learning import ChatMessage, LearningPlan, LLMCallLog, NegotiationLog, PracticeRecord, UserGoalSetting
from .message import Conversation, Message
from .intelligence import AIPregrade, StudentHelpSignal, TeacherAIPreference, TeacherExperience, TeachingArtifact, TeachingRisk
from .revamp import CommentUpvote, CourseRelation, QuestionComment, UserAIProfile, UserCourse
from .side import LearningResource, NoteAttachment, UserNote, UserNotification, UserPreference
from .teaching import (
    AdviceDraft,
    Assignment,
    AssignmentAnswer,
    AssignmentAttempt,
    AssignmentQuestion,
    Class,
    ClassMember,
    TeacherStudentMessage,
)
from .user import AuditLog, AuthSession, TeacherInviteCode, TeacherProfile, User


__all__ = [
    "AnswerAttachment",
    "AIPregrade",
    "AdviceDraft",
    "AssessmentSession",
    "AssessmentSessionQuestion",
    "Assignment",
    "AssignmentAnswer",
    "AssignmentAttempt",
    "AssignmentQuestion",
    "AuditLog",
    "AuthSession",
    "Base",
    "ChatMessage",
    "Class",
    "ClassMember",
    "Conversation",
    "CourseRelation",
    "CommentUpvote",
    "KnowledgeNode",
    "LearningPlan",
    "LearningResource",
    "LLMCallLog",
    "MathCourse",
    "MathStage",
    "Message",
    "MistakeTag",
    "NegotiationLog",
    "NoteAttachment",
    "PracticeRecord",
    "Question",
    "QuestionComment",
    "QuestionAttachment",
    "SourceAttribution",
    "TeacherInviteCode",
    "TeacherAIPreference",
    "TeacherExperience",
    "TeacherProfile",
    "TeacherStudentMessage",
    "TeachingArtifact",
    "TeachingRisk",
    "UploadedFile",
    "User",
    "UserAIProfile",
    "UserCourse",
    "UserGoalSetting",
    "UserNote",
    "UserNotification",
    "UserPreference",
    "StudentHelpSignal",
]
