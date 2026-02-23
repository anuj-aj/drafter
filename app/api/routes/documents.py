from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app.schemas.document import (
    CreateDocumentRequest,
    UpdateDocumentRequest,
    DocumentResponse,
)
from app.services.document_service import create_document, update_document, get_document
from app.exceptions import DocumentNotFoundError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse)
def create(payload: CreateDocumentRequest, db: Session = Depends(get_db)):
    return create_document(db, payload.title)


@router.get("/{document_id}", response_model=DocumentResponse)
def read(document_id: str, db: Session = Depends(get_db)):
    doc = get_document(db, document_id)
    if not doc:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return doc


@router.put("/{document_id}", response_model=DocumentResponse)
def update(document_id: str, payload: UpdateDocumentRequest, db: Session = Depends(get_db)):
    return update_document(db, document_id, payload.content)