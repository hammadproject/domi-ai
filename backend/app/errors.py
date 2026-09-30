"""One consistent error schema for every non-streaming failure:

{"error": {"code": "...", "message": "...", "request_id": "...", "details": [...]}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

HIGH_DEMAND_MESSAGE = "We're seeing high demand right now. Please try again later."


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class HighDemandError(AppError):
    """Daily LLM budget used up: degrade gracefully instead of failing on Gemini's 429."""

    status_code = 503
    code = "high_demand"

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(HIGH_DEMAND_MESSAGE, retry_after=retry_after)


def error_body(
    code: str, message: str, request_id: str | None, details: list[Any] | None = None
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details:
        err["details"] = details
    return {"error": err}


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _response(status: int, body: dict[str, Any], retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(max(1, retry_after))} if retry_after is not None else None
    return JSONResponse(status_code=status, content=body, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        body = error_body(exc.code, exc.message, _rid(request))
        return _response(exc.status_code, body, exc.retry_after)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # loc / msg / type only: never echo the submitted input back (it could hold secrets)
        details = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
            for e in exc.errors()
        ]
        body = error_body("validation_error", "Invalid request.", _rid(request), details)
        return _response(422, body)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 422: "validation_error"}
        code = codes.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _response(exc.status_code, error_body(code, message, _rid(request)))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        body = error_body("internal_error", "Something went wrong.", _rid(request))
        return _response(500, body)
