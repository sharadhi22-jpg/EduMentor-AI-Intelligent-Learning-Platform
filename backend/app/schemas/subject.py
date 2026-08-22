from datetime import datetime
from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Computer Networks"])
    code: str | None = Field(None, max_length=20, examples=["CS-601"])
    semester: int = Field(..., ge=1, le=8, description="Semester must be between 1 and 8")


class SubjectOut(BaseModel):
    id: int
    name: str
    code: str | None
    semester: int
    user_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True
