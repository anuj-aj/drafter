class DocumentNotFoundError(Exception):
    """Raised when a requested document cannot be found.

    Use this when lookups by id or other identifiers return no result.
    """



class EmptyContentError(Exception):
    """Raised when an operation requires content but none was provided.

    Examples: creating or revising a document with empty text.
    """



class RevisionError(Exception):
    """Raised for errors related to document revisions.

    Use for conflicts, invalid revision numbers, or failed updates.
    """

class InvariantViolationError(Exception):
    """Raised when an internal invariant is violated.

    Indicates a bug or unexpected state that should be investigated.
    """


class ExternalServiceError(Exception):
    """Raised when an external dependency (LLM, API, etc.) is unavailable or fails.

    This separates external service failures from internal invariants so callers
    can handle them differently (e.g. retry, surface friendly message).
    """
    pass

