"""Structured JSON logging with request ids and secret redaction."""

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

MASK = "***"
# Shapes of secrets we use, redacted even if the exact value isn't in settings.
_PATTERNS = [
    re.compile(r"sk-lf-[\w-]+"),  # Langfuse secret key
    re.compile(r"pk-lf-[\w-]+"),  # Langfuse public key
    re.compile(r"AIza[\w-]{20,}"),  # Google API key (classic format)
    re.compile(r"\bAQ\.[\w-]{20,}"),  # Google AI Studio key (current format)
    re.compile(r"(?i)(x-api-key|x-goog-api-key|authorization)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)(=)[^&\s'\"]+"),
]
_URL_CREDENTIALS = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^:/@\s]+:)[^@\s]+(@)")


def _secret_values() -> list[str]:
    from app.config import get_settings

    s = get_settings()
    candidates = [
        s.rentcast_api_key.get_secret_value(),
        s.gemini_api_key.get_secret_value(),
        s.langfuse_secret_key.get_secret_value(),
        s.langfuse_public_key,
        s.database_url,
        s.redis_url,
    ]
    # longest first so a full URL is masked before any piece of it
    return sorted((v for v in candidates if v and len(v) >= 8), key=len, reverse=True)


def redact(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, MASK)
    text = _URL_CREDENTIALS.sub(rf"\1{MASK}\2", text)
    for pattern in _PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(rf"\1\2{MASK}", text)
        elif pattern.groups == 1:
            text = pattern.sub(rf"\1={MASK}", text)
        else:
            text = pattern.sub(MASK, text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload))


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Library loggers that print full request URLs or are simply noisy at INFO.
    for noisy in ("httpx", "httpcore", "urllib3", "google_genai", "google.auth", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Prints an identical "AFC is not recommended" warning on every generate call.
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    # We emit our own JSON access log line; uvicorn's plain-text one would duplicate it.
    logging.getLogger("uvicorn.access").disabled = True


access_log = logging.getLogger("app.access")


class RequestContextMiddleware:
    """Pure ASGI (not BaseHTTPMiddleware) so the request id stays set while a streamed
    response body is still being produced, and so every request gets an access-log line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")[:64]
        rid = incoming if re.fullmatch(r"[\w.-]{8,64}", incoming or "") else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            client = scope.get("client")
            access_log.info(
                "request",
                extra={
                    "fields": {
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "client": client[0] if client else None,
                    }
                },
            )
            request_id_var.reset(token)
