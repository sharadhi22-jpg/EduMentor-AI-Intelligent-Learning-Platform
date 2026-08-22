from datetime import datetime
from pydantic import BaseModel, Field
from app.models.study import DifficultyLevel


class FlashcardOut(BaseModel):
    id: int
    subject_id: int
    document_id: int | None
    front: str
    back: str
    difficulty: DifficultyLevel
    created_at: datetime

    class Config:
        from_attributes = True


class FlashcardGenerateRequest(BaseModel):
    subject_id: int
    document_id: int | None = None
    count: int = Field(5, ge=1, le=20)
    difficulty: DifficultyLevel = DifficultyLevel.medium


class QuizOut(BaseModel):
    id: int
    subject_id: int
    document_id: int | None
    title: str
    difficulty: DifficultyLevel
    questions: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class QuizGenerateRequest(BaseModel):
    subject_id: int
    document_id: int | None = None
    count: int = Field(5, ge=1, le=15)
    difficulty: DifficultyLevel = DifficultyLevel.medium


class QuizSubmitRequest(BaseModel):
    # Mapping of question index to user's answer string
    answers: dict[int, str]


class QuizAttemptOut(BaseModel):
    id: int
    quiz_id: int
    user_id: int
    score: int
    total_questions: int
    answers: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class StudyTimeLogRequest(BaseModel):
    subject_id: int
    hours: float = Field(..., gt=0, le=24, description="Hours of study to add, must be > 0")


class ProgressOut(BaseModel):
    id: int
    user_id: int
    subject_id: int
    study_hours: float
    completed_quizzes: int
    weak_topics: list[str] | None
    strong_topics: list[str] | None
    updated_at: datetime

    class Config:
        from_attributes = True
