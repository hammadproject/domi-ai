import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.cities import router as cities_router
from app.api.compare import router as compare_router
from app.api.health import router as health_router
from app.api.listings import router as listings_router
from app.api.mortgage import router as mortgage_router
from app.config import get_settings
from app.errors import register_error_handlers
from app.observability.logging import RequestContextMiddleware, setup_logging

setup_logging()
log = logging.getLogger(__name__)

settings = get_settings()
origins = settings.cors_origin_list
if "*" in origins:
    log.warning("CORS_ORIGINS contains '*': restrict it to your frontend's origin in production")

app = FastAPI(title="Domi API")
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,  # no cookies/sessions: the session id travels in the request body
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)
# Added last = outermost, so even CORS preflights and error responses get a request id + log line.
app.add_middleware(RequestContextMiddleware)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(listings_router)
app.include_router(cities_router)
app.include_router(compare_router)
app.include_router(mortgage_router)
