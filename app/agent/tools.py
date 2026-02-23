from langchain_core.tools import tool
from app.services.document_service import update_document, get_document, save_draft
from sqlalchemy.orm import Session
from app.exceptions import DocumentNotFoundError, EmptyContentError
import logging

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

        if content.strip() == doc.content.strip():
            logger.info(f"No changes detected for document {document_id}")
            return {"status": "noop", "message": "No changes suggested"}

        # Save proposal as draft so subsequent interactions see the updated content
        draft = save_draft(db, document_id, content)
        logger.info(f"Draft proposal saved for document {document_id} (draft_id={draft.id})")
        return {"status": "proposal", "proposed_content": content, "draft_id": str(draft.id)}

    tools = [propose_update]

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