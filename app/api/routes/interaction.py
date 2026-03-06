from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, ToolMessage
import logging
import re

from app.api.dependencies import get_db
from app.schemas.interaction import InteractionRequest, InteractionResponse
from app.services.document_service import get_document
from app.services.document_service import get_draft, apply_draft
from app.agent.graph import build_graph
from app.exceptions import (
    DocumentNotFoundError,
    InvariantViolationError,
    ExternalServiceError
)



router = APIRouter(prefix="/documents", tags=["interaction"])

logger = logging.getLogger(__name__)


def _is_confirmation_input(user_input: str) -> bool:
    """True only when the user is clearly confirming/applying a draft.

    This avoids substring matches like "don't save" triggering an apply.
    """
    text = (user_input or "").strip().lower()
    if not text:
        return False

    cleaned = re.sub(r"[^a-z0-9\s']+", " ", text)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return False

    confirmation_tokens = {"yes", "ok", "okay", "apply", "save", "confirm", "proceed"}
    negation_tokens = {"no", "not", "dont", "don't", "never"}

    if any(t in negation_tokens for t in tokens):
        return False

    if not any(t in confirmation_tokens for t in tokens):
        return False

    # Confirmations are typically short ("save", "yes", "yes save").
    return len(tokens) <= 3


@router.post("/{document_id}/interact", response_model=InteractionResponse)
def interact(document_id: str, payload: InteractionRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /interact called for document {document_id}")
    logger.debug(f"User input: {payload.user_input[:100]}")

    doc_before = get_document(db, document_id)
    if not doc_before:
        logger.warning(f"Document {document_id} not found")
        raise DocumentNotFoundError(f"Document {document_id} not found")

    version_before = doc_before.version
    logger.info(f"Document {document_id} retrieved (version={version_before})")

    # If there is a draft in progress, use its content as the document content
    draft = get_draft(db, document_id)
    doc_content_for_session = draft.content if draft else doc_before.content
    if draft:
        logger.info(f"Using existing draft for document {document_id} (draft_id={draft.id})")
    else:
        logger.info(f"No draft found; using current document content for {document_id}")

    # Check if user is confirming the draft (tight detection to avoid false positives)
    is_confirmation = _is_confirmation_input(payload.user_input)

    if draft and is_confirmation:
        logger.info(f"Confirmation detected for document {document_id}; applying draft")
        # User confirmed the draft; apply it
        try:
            updated = apply_draft(db, document_id, expected_version=version_before)
            logger.info(f"Draft applied for document {document_id}, new version={updated.version}")
            return {"response": f"Changes saved. Document updated to version {updated.version}."}
        except Exception as e:
            logger.error(f"Failed to apply draft for document {document_id}: {e}", exc_info=True)
            raise InvariantViolationError(str(e)) from e

    graph = build_graph(db, document_id, doc_content_for_session)
    logger.debug(f"Graph built for document {document_id}")

    state = {
        "messages": [HumanMessage(content=payload.user_input)],
        "document_id": str(document_id),
        "document_content": doc_content_for_session
    }

    try:
        logger.debug(f"Invoking graph for document {document_id}")
        result = graph.invoke(
            state,
            config={"recursion_limit": 5}
        )
        logger.debug(f"Graph invocation complete for document {document_id}")

    except Exception as e:
        logger.exception(f"LLM/agent invocation failed for document {document_id}")
        raise ExternalServiceError(f"LLM service unavailable: {e}") from e


    messages = result.get("messages", [])
    if not messages:
        logger.error(f"Agent returned empty message list for document {document_id}")
        raise InvariantViolationError("Agent returned empty message list")

    final_message = messages[-1]
    logger.debug(f"Final message from agent for document {document_id}: {str(final_message)[:100]}")

    # Check if a tool was called (proposal made)
    tool_called = any(isinstance(m, ToolMessage) for m in messages)
    if tool_called:
        logger.info(f"Tool call detected for document {document_id}")

    # Re-fetch the draft after agent run since propose_update persists it.
    draft_after = get_draft(db, document_id)

    # Also return draft info (the actual proposed content) if present so clients can display it.
    response = {"response": final_message.content}
    if draft_after:
        response["draft"] = {
            "draft_id": str(draft_after.id),
            "document_id": str(document_id),
            "content": draft_after.content,
            "note": (
                "✓ Proposal saved as draft. Say 'yes'/'save' to apply." if tool_called else "Draft exists for this document."
            ),
        }
        logger.info(f"Draft content included in response for document {document_id}")

    return response



@router.post("/{document_id}/apply-update")
def apply_update(document_id: str, payload: dict, db: Session = Depends(get_db)):
    """Apply the current draft to the document.

    Payload may include `expected_version` to guard against races.
    """
    logger.info(f"POST /apply-update called for document {document_id}")
    expected_version = payload.get("expected_version")
    try:
        updated = apply_draft(db, document_id, expected_version=expected_version)
        logger.info(f"Draft applied successfully for document {document_id}, new version={updated.version}")
    except Exception as e:
        logger.error(f"Failed to apply draft for document {document_id}: {e}", exc_info=True)
        raise InvariantViolationError(str(e)) from e

    return {
        "status": "success",
        "new_version": updated.version,
        "response": f"Changes saved. Document updated to version {updated.version}.",
        "document": {
            "id": str(updated.id),
            "title": updated.title,
            "content": updated.content,
            "version": updated.version,
        },
    }


@router.get("/{document_id}/draft")
def get_draft_endpoint(document_id: str, db: Session = Depends(get_db)):
    """Retrieve the current draft for a document."""
    logger.info(f"GET /draft called for document {document_id}")
    doc = get_document(db, document_id)
    if not doc:
        logger.warning(f"Document {document_id} not found")
        raise DocumentNotFoundError(f"Document {document_id} not found")

    draft = get_draft(db, document_id)
    if not draft:
        logger.info(f"No draft found for document {document_id}")
        return {"status": "no_draft", "message": "No draft in progress for this document"}

    logger.info(f"Draft retrieved for document {document_id} (draft_id={draft.id})")
    return {
        "draft_id": str(draft.id),
        "document_id": str(document_id),
        "content": draft.content,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat()
    }
    