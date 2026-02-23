from fastapi.responses import JSONResponse
from fastapi import Request
from app.exceptions import (
    DocumentNotFoundError,
    EmptyContentError,
    InvariantViolationError,
    ExternalServiceError,
)


def register_exception_handlers(app):

    @app.exception_handler(DocumentNotFoundError)
    async def handle_not_found(request: Request, exc: DocumentNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(EmptyContentError)
    async def handle_empty_content(request: Request, exc: EmptyContentError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )


    @app.exception_handler(InvariantViolationError)
    async def handle_invariant_error(request: Request, exc: InvariantViolationError):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )


    @app.exception_handler(ExternalServiceError)
    async def handle_external_service_error(request: Request, exc: ExternalServiceError):
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc) or "External service unavailable"},
        )