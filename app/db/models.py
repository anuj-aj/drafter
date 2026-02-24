from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .session import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    revisions = relationship("Revision", back_populates="document")


class Revision(Base):
    __tablename__ = "revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    content = Column(Text)
    version = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="revisions")


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), unique=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# Audit table for logging interactions
class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    user_input = Column(Text)
    tool_used = Column(String)  # Changed to String for tool name or identifier
    version_before = Column(Integer)
    version_after = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document")