from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content: str
    version: int
    created_at: datetime

    class Config:
        orm_mode = True


class RevisionResponse(BaseModel):
    id: UUID
    document_id: UUID
    content: Optional[str]
    version: int
    created_at: datetime

    class Config:
        orm_mode = True


class CreateDocumentRequest(BaseModel):
    title: str


class UpdateDocumentRequest(BaseModel):
    content: str
