from sqlalchemy.orm import Session
from app.db.models import Document, Revision, InteractionLog
from datetime import datetime
from app.exceptions import DocumentNotFoundError, EmptyContentError
from typing import Optional
from app.db.models import Draft
from sqlalchemy.exc import NoResultFound
import logging

logger = logging.getLogger(__name__)


def create_document(db: Session, title: str) -> Document:
    logger.info(f"Creating document with title: {title}")
    doc = Document(title=title, content="", version=1)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(f"Document created with id: {doc.id}")
    return doc


def get_document(db: Session, document_id: str) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return doc


def update_document(db: Session, document_id: str, new_content: str, user_input: str = None, tool_used: str = None) -> Document:
    logger.info(f"Updating document {document_id} (version {get_document(db, document_id).version})")
    doc = get_document(db, document_id)
    version_before = doc.version

    if not new_content.strip():
        logger.warning(f"Attempted update with blank content for document {document_id}")
        raise EmptyContentError("Content cannot be blank")

    # Save previous revision
    revision = Revision(
        document_id=doc.id,
        content=doc.content,
        version=doc.version,
    )

    db.add(revision)
    logger.debug(f"Created revision v{doc.version} for document {document_id}")

    # Update document
    doc.content = new_content
    doc.version += 1

    db.commit()
    db.refresh(doc)
    logger.info(f"Document {document_id} updated to version {doc.version}")

    # Log interaction
    interaction_log = InteractionLog(
        document_id=doc.id,
        user_input=user_input,
        tool_used=tool_used,
        version_before=version_before,
        version_after=doc.version,
        created_at=datetime.utcnow(),
    )
    db.add(interaction_log)
    db.commit()
    return doc


def get_revisions(db: Session, document_id: str):
    return (
        db.query(Revision)
        .filter(Revision.document_id == document_id)
        .order_by(Revision.version.desc())
        .all()
    )


def get_draft(db: Session, document_id: str) -> Optional[Draft]:
    return db.query(Draft).filter(Draft.document_id == document_id).first()


def save_draft(db: Session, document_id: str, content: str, user_input: str = None, tool_used: str = None) -> Draft:
    draft = get_draft(db, document_id)
    now = datetime.utcnow()
    if draft:
        draft.content = content
        draft.updated_at = now
    else:
        draft = Draft(document_id=document_id, content=content, created_at=now, updated_at=now)
        db.add(draft)

    # Log interaction
    interaction_log = InteractionLog(
        document_id=document_id,
        user_input=user_input,
        tool_used=tool_used,
        version_before=None,
        version_after=None,
        created_at=now,
    )
    db.add(interaction_log)

    db.commit()
    db.refresh(draft)
    return draft


def delete_draft(db: Session, document_id: str):
    draft = get_draft(db, document_id)
    if draft:
        db.delete(draft)
        db.commit()


def apply_draft(db: Session, document_id: str, expected_version: Optional[int] = None):
    logger.info(f"Applying draft for document {document_id} (expected_version={expected_version})")
    doc = get_document(db, document_id)
    draft = get_draft(db, document_id)
    if not draft:
        logger.error(f"No draft found for document {document_id}")
        raise DocumentNotFoundError(f"No draft found for document {document_id}")

    if expected_version is not None and doc.version != expected_version:
        logger.warning(f"Version mismatch for document {document_id}: expected {expected_version}, got {doc.version}")
        raise RevisionError("Version mismatch")

    # Persist draft content via existing update_document
    updated = update_document(db, document_id, draft.content)

    # Remove the draft
    delete_draft(db, document_id)
    logger.info(f"Draft applied and deleted for document {document_id}")
    return updated