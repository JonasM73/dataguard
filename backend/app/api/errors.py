"""Format d'erreur unique de l'API.

Toutes les erreurs sortent sous la même forme `{"error": {...}}` : le frontend
n'a alors qu'un seul cas à traiter, quelle que soit l'origine du problème.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.core.logging import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: Any | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(resource: str, identifier: Any) -> APIError:
    return APIError(
        status.HTTP_404_NOT_FOUND,
        f"{resource}_not_found",
        f"{resource.capitalize()} {identifier} introuvable",
    )


def _payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            content=_payload(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            content=jsonable_encoder(
                _payload("invalid_request", "Requête invalide.", exc.errors())
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        # L'identifiant de trace est renvoyé pour relier l'erreur vue par
        # l'utilisateur à la trace correspondante côté serveur.
        span = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span else None
        logger.exception("api.unexpected_error", trace_id=trace_id)
        return JSONResponse(
            content=_payload("internal_error", "Erreur interne.", {"trace_id": trace_id}),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
