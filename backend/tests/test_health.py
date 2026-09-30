import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.main import app


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionError("boom secret-host")


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    from app.config import get_settings

    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def test_health_ok(client, monkeypatch) -> None:
    monkeypatch.setattr(health, "check_db", _ok)
    monkeypatch.setattr(health, "check_redis", _ok)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["x-request-id"]


def test_health_reports_failing_dependency(client, monkeypatch) -> None:
    monkeypatch.setattr(health, "check_db", _ok)
    monkeypatch.setattr(health, "check_redis", _fail)
    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["checks"]["redis"] == "error: ConnectionError"
    assert body["checks"]["database"] == "ok"
    assert "secret-host" not in r.text
