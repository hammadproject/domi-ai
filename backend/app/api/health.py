import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import check_db
from app.redis import check_redis

router = APIRouter()
log = logging.getLogger(__name__)


async def _run(check: Callable[[], Awaitable[None]]) -> str:
    try:
        await check()
    except Exception as exc:  # report the class only, never connection details
        log.warning("health check failed: %s", type(exc).__name__)
        return f"error: {type(exc).__name__}"
    return "ok"


async def _check_llm_config() -> None:
    s = get_settings()
    if not s.gemini_api_key.get_secret_value() or not s.llm_model:
        raise RuntimeError("LLM not configured")


@router.get("/health")
async def health() -> JSONResponse:
    checks = {
        "database": await _run(check_db),
        "redis": await _run(check_redis),
        "llm_config": await _run(_check_llm_config),
    }
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "checks": checks},
    )
