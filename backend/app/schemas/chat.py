from datetime import datetime
from pydantic import BaseModel
from app.models.chat import ChatRole


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    session_id: str
    role: ChatRole
    content: str
    citations: list[dict] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    subject_id: int
    title: str | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    user_id: int
    subject_id: int
    created_at: datetime

    class Config:
        from_attributes = True
