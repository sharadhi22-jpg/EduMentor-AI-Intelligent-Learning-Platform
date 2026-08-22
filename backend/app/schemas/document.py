from datetime import datetime
from pydantic import BaseModel
from app.models.document import UploadStatus


class DocumentOut(BaseModel):
    id: int
    filename: str
    filepath: str
    file_type: str
    size_bytes: int
    upload_status: UploadStatus
    subject_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentChunkOut(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str

    class Config:
        from_attributes = True
