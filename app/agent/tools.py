from langchain_core.tools import tool
from app.services.document_service import update_document, get_document, get_draft, save_draft
from sqlalchemy.orm import Session
from app.exceptions import DocumentNotFoundError, EmptyContentError
import logging
import difflib

logger = logging.getLogger(__name__)


def build_tools(db: Session, document_id: str, allow_persist: bool = False):
    """Build tools for the agent.

    By default (`allow_persist=False`) the returned tools are non-destructive
    and only provide proposals. When `allow_persist=True` the destructive
    `update` tool is included for explicit server-side application.
    """

    @tool
    def propose_update(content: str) -> dict:
        """Return a proposal for updating the document without persisting it.

        The agent should call this to suggest new content. The caller (API)
        is responsible for asking the user to confirm before persisting.
        """
        logger.debug(f"propose_update called for document {document_id}")
        try:
            doc = get_document(db, document_id)
        except DocumentNotFoundError as e:
            logger.warning(f"Document not found: {document_id}")
            return {"status": "error", "message": str(e)}

        if not content or not content.strip():
            logger.warning(f"Blank content proposed for document {document_id}")
            return {"status": "error", "message": "Proposed content is blank"}

        # Guardrail: The agent is required to submit the FULL updated document.
        # If it submits only a small fragment (e.g., just the new paragraph),
        # we'd overwrite the existing draft and lose prior edits.
        existing_draft = get_draft(db, document_id)
        base_content = (existing_draft.content if existing_draft else doc.content) or ""

        def _normalize(text: str) -> str:
            return " ".join((text or "").split())

        base_norm = _normalize(base_content)
        content_norm = _normalize(content)

        if base_norm:
            # Heuristics: reject proposals that are much shorter than the base
            # or wildly dissimilar, which strongly suggests the model dropped content.
            too_short = len(content_norm) < int(len(base_norm) * 0.70)
            similarity = difflib.SequenceMatcher(None, base_norm, content_norm).ratio()
            too_dissimilar = len(base_norm) > 200 and similarity < 0.55

            if too_short or too_dissimilar:
                logger.warning(
                    "Proposed update appears to omit existing content "
                    f"(base_len={len(base_norm)}, proposed_len={len(content_norm)}, similarity={similarity:.2f})"
                )
                return {
                    "status": "error",
                    "message": (
                        "Proposed update appears to drop existing document/draft content. "
                        "You must call propose_update with the FULL updated document text, "
                        "including all existing content plus the requested changes."
                    ),
                }

        if content.strip() == doc.content.strip():
            logger.info(f"No changes detected for document {document_id}")
            return {"status": "noop", "message": "No changes suggested"}

        # Save proposal as draft so subsequent interactions see the updated content
        draft = save_draft(db, document_id, content)
        logger.info(f"Draft proposal saved for document {document_id} (draft_id={draft.id})")
        return {"status": "proposal", "proposed_content": content, "draft_id": str(draft.id)}

    @tool
    def propose_append(addition: str) -> dict:
        """Append new content to the current draft (or document if no draft).

        Use this for requests like "add info about X" where the safest behavior
        is to keep all existing draft content and append the new material.
        """
        logger.debug(f"propose_append called for document {document_id}")
        try:
            doc = get_document(db, document_id)
        except DocumentNotFoundError as e:
            logger.warning(f"Document not found: {document_id}")
            return {"status": "error", "message": str(e)}

        if not addition or not addition.strip():
            return {"status": "error", "message": "Appended content is blank"}

        existing_draft = get_draft(db, document_id)
        base_content = (existing_draft.content if existing_draft else doc.content) or ""

        new_content = base_content.rstrip()
        if new_content:
            new_content += "\n\n"
        new_content += addition.strip()

        draft = save_draft(db, document_id, new_content)
        logger.info(f"Draft appended for document {document_id} (draft_id={draft.id})")
        return {
            "status": "proposal",
            "proposed_content": new_content,
            "draft_id": str(draft.id),
        }

    tools = [propose_update, propose_append]

    if allow_persist:
        @tool
        def update(content: str) -> dict:
            """Persistently update the document (creates revision and increments version)."""
            try:
                doc = update_document(db, document_id, content)
                return {"status": "success", "new_version": doc.version}

            except DocumentNotFoundError as e:
                return {"status": "error", "message": str(e)}

            except EmptyContentError as e:
                return {"status": "error", "message": str(e)}

            except Exception:
                return {"status": "error", "message": "Unexpected error"}

        tools.append(update)

    return tools