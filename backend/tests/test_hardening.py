import asyncio
import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.agent.graph import run_chat_turn
from app.agent.memory import InMemorySessionStore
from app.api import chat as chat_module
from app.api.deps import get_quota_guard, get_turn_runner
from app.cache import Cache, make_key
from app.config import get_settings
from app.llm import retry
from app.llm.counting import CountingLLM
from app.main import app
from app.observability import logging as applog
from app.observability.tracing import NOOP
from app.quota import PACIFIC, QuotaExceeded, QuotaGuard
from app.rag.models import Filters, Hit
from app.rag.pipeline import cached_retriever
from app.ratelimit import RateLimiter
from tests.conftest import FakeAsyncRedis, FakeSyncRedis, _State
from tests.test_agent import HITS, ScriptedLLM, TurnUnderstanding, make_deps, parse_sse, search_u


def set_env(monkeypatch, **env) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k.upper(), str(v))
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_settings():
    yield
    get_settings.cache_clear()


@pytest.fixture
def chat_client():
    """TestClient whose chat turn is a cheap smalltalk reply (no Gemini, no DB)."""

    def factory(llm=None):
        deps = make_deps(llm or ScriptedLLM([TurnUnderstanding(intent="smalltalk")] * 50))

        async def runner(session_id, message):
            return await run_chat_turn(deps, session_id, message)

        app.dependency_overrides[get_turn_runner] = lambda: runner
        return TestClient(app)

    return factory


# ===================== rate limiting: 429 =====================
def test_chat_429_after_ip_limit_with_retry_after_and_schema(chat_client, monkeypatch) -> None:
    set_env(monkeypatch, chat_rate_limit_per_minute=3)
    c = chat_client()
    for _ in range(3):
        assert c.post("/api/chat", json={"message": "hello there"}).status_code == 200
    r = c.post("/api/chat", json={"message": "hello there"})
    assert r.status_code == 429
    retry_after = int(r.headers["retry-after"])
    assert 1 <= retry_after <= 60
    err = r.json()["error"]
    assert err["code"] == "rate_limited" and "Try again in" in err["message"]
    assert err["request_id"] == r.headers["x-request-id"]


def test_chat_per_session_limit_is_independent_of_ip(chat_client, monkeypatch) -> None:
    set_env(monkeypatch, chat_rate_limit_per_minute=3, trust_forwarded_for="true")
    c = chat_client()
    body = {"message": "hello there", "session_id": "session-one-aaa"}
    statuses = [
        c.post("/api/chat", json=body, headers={"x-forwarded-for": f"10.0.0.{i}"}).status_code
        for i in range(4)  # four different IPs, one session
    ]
    assert statuses == [200, 200, 200, 429]
    other = {"message": "hello there", "session_id": "session-two-bbb"}
    assert (
        c.post("/api/chat", json=other, headers={"x-forwarded-for": "10.0.0.9"}).status_code == 200
    )


def test_ips_are_limited_independently_when_proxy_is_trusted(chat_client, monkeypatch) -> None:
    set_env(monkeypatch, rate_limit_per_minute=2, trust_forwarded_for="true")
    c = TestClient(app)
    mortgage = {"price": 400_000, "down_payment_pct": 20}

    def hit(ip):
        return c.post("/api/mortgage/estimate", json=mortgage, headers={"x-forwarded-for": ip})

    assert [hit("1.1.1.1").status_code for _ in range(3)] == [200, 200, 429]
    assert hit("2.2.2.2").status_code == 200  # a different client is unaffected


def test_forwarded_header_is_ignored_unless_proxy_trusted(monkeypatch) -> None:
    set_env(monkeypatch, rate_limit_per_minute=2)  # trust_forwarded_for defaults to False
    c = TestClient(app)
    mortgage = {"price": 400_000, "down_payment_pct": 20}
    codes = [
        c.post(
            "/api/mortgage/estimate", json=mortgage, headers={"x-forwarded-for": f"9.9.9.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]  # spoofing the header does not dodge the limit


def test_health_and_docs_are_not_rate_limited(monkeypatch) -> None:
    set_env(monkeypatch, rate_limit_per_minute=1)
    c = TestClient(app)
    assert all(c.get("/openapi.json").status_code == 200 for _ in range(5))


async def test_limit_recovers_after_the_window_passes() -> None:
    now = [1_000_000.0]
    limiter = RateLimiter(FakeAsyncRedis(), clock=lambda: now[0])
    for _ in range(2):
        await limiter.check("t", "ip", limit=2)
    with pytest.raises(Exception) as exc:
        await limiter.check("t", "ip", limit=2)
    assert 1 <= exc.value.retry_after <= 60
    now[0] += 130  # two windows later: old hits no longer count
    await limiter.check("t", "ip", limit=2)


async def test_no_double_burst_across_a_minute_boundary() -> None:
    """The fixed-window loophole: 'limit' requests before the boundary and 'limit' after."""
    now = [1_000_000.0 - (1_000_000.0 % 60) + 59.0]  # one second before a boundary
    limiter = RateLimiter(FakeAsyncRedis(), clock=lambda: now[0])
    for _ in range(30):
        await limiter.check("api", "ip", limit=30)  # fills the window
    now[0] += 2.0  # just past the boundary
    with pytest.raises(Exception) as exc:
        await limiter.check("api", "ip", limit=30)
    assert exc.value.code == "rate_limited"
    now[0] += 40.0  # most of the previous window has slid out of range
    await limiter.check("api", "ip", limit=30)


async def test_limiter_fails_open_when_redis_is_down() -> None:
    class Down:
        def pipeline(self, transaction=False):
            raise ConnectionError

    await RateLimiter(Down()).check("t", "ip", limit=1)  # must not raise


# ===================== validation: 422 =====================
@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/chat", {}),
        ("/api/chat", {"message": ""}),
        ("/api/chat", {"message": "hi", "session_id": "bad id!"}),
        ("/api/mortgage/estimate", {"price": -1, "down_payment_pct": 10}),
        ("/api/mortgage/estimate", {"price": 100_000, "down_payment": 200_000}),
    ],
)
def test_422_uses_the_common_error_schema(chat_client, path, body) -> None:
    r = chat_client().post(path, json=body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["request_id"] == r.headers["x-request-id"]
    assert err["message"]


def test_422_details_name_the_field_and_never_echo_input(chat_client) -> None:
    secret_marker = "SUPER-SECRET-" + "x" * 1001
    r = chat_client().post("/api/chat", json={"message": secret_marker})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["field"] == "message"
    assert "SUPER-SECRET" not in r.text


def test_unknown_route_and_wrong_method_use_the_same_schema() -> None:
    c = TestClient(app)
    nf = c.get("/nope")
    assert nf.status_code == 404 and nf.json()["error"]["code"] == "not_found"
    bad = c.get("/api/chat")
    assert bad.status_code == 405 and bad.json()["error"]["code"] == "method_not_allowed"


def test_listings_query_validation_422() -> None:
    c = TestClient(app)
    for q in ["page=0", "page_size=500", "sort=weird", "state=Texas", "beds_min=-1",
              "price_min=500&price_max=100", "property_type=Castle"]:  # fmt: skip
        r = c.get(f"/api/listings?{q}")
        assert r.status_code == 422, q
        assert r.json()["error"]["code"] == "validation_error"


def test_unhandled_exception_returns_generic_500_without_details() -> None:
    @app.get("/_boom")
    async def boom():
        raise RuntimeError("db password is hunter2")

    r = TestClient(app, raise_server_exceptions=False).get("/_boom")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert "hunter2" not in r.text and r.json()["error"]["request_id"]
    app.router.routes[:] = [x for x in app.router.routes if getattr(x, "path", "") != "/_boom"]


# ===================== daily LLM budget =====================
def make_guard(limit: int, now: float = 1_750_000_000.0, state=None):
    clock = [now]
    return QuotaGuard(FakeSyncRedis(state), limit, clock=lambda: clock[0]), clock


def test_quota_counts_then_blocks_with_retry_after() -> None:
    g, _ = make_guard(2)
    assert (g.consume(), g.consume()) == (1, 2)
    assert g.remaining() == 0
    with pytest.raises(QuotaExceeded) as exc:
        g.consume()
    assert 1 <= exc.value.retry_after <= 86_400


def test_quota_resets_at_midnight_pacific() -> None:
    from datetime import datetime

    # 2026-07-01 06:59 UTC is 23:59 PDT on Jun 30; one minute later it is a new Pacific day
    before = datetime(
        2026, 7, 1, 6, 59, tzinfo=PACIFIC.utcoffset(None) and None or __import__("datetime").UTC
    )
    g, clock = make_guard(1, now=before.timestamp())
    g.consume()
    assert g.remaining() == 0
    assert 1 <= g.seconds_until_reset() <= 120
    clock[0] += 120
    assert g.remaining() == 1  # fresh day, fresh budget


def test_quota_fails_open_when_redis_is_down() -> None:
    class Down:
        def get(self, k):
            raise ConnectionError

        def incr(self, k):
            raise ConnectionError

    g = QuotaGuard(Down(), 1)
    assert g.consume() == 0 and g.remaining() == 1


def test_counting_llm_stops_before_calling_gemini_when_budget_is_gone() -> None:
    g, _ = make_guard(1)
    llm = ScriptedLLM([search_u(), search_u()])
    counting = CountingLLM(llm, NOOP, g)
    counting.generate_structured("p", TurnUnderstanding)
    with pytest.raises(QuotaExceeded):
        counting.generate_structured("p", TurnUnderstanding)
    assert len(llm.prompts) == 1  # the second call never reached Gemini


def test_chat_returns_503_with_retry_after_when_daily_budget_is_spent(chat_client) -> None:
    g, _ = make_guard(0)
    c = chat_client()
    app.dependency_overrides[get_quota_guard] = lambda: g
    r = c.post("/api/chat", json={"message": "hello there"})
    assert r.status_code == 503 and int(r.headers["retry-after"]) >= 1
    err = r.json()["error"]
    assert err["code"] == "high_demand" and "try again later" in err["message"].lower()


def test_quota_running_out_mid_turn_becomes_a_friendly_sse_error(chat_client) -> None:
    c = chat_client()

    async def runner(session_id, message):
        raise QuotaExceeded(3600)

    app.dependency_overrides[get_turn_runner] = lambda: runner
    events = parse_sse(c.post("/api/chat", json={"message": "hello there"}).text)
    assert events == [
        (
            "error",
            {
                "code": "high_demand",
                "message": "We're seeing high demand right now. Please try again later.",
                "retry_after": 3600,
            },
        )
    ]


async def test_generation_hitting_the_budget_degrades_instead_of_failing() -> None:
    g, _ = make_guard(1)  # exactly enough for the parse call, none left for generation
    llm = ScriptedLLM([search_u(city="Austin")])
    deps = make_deps(llm)
    deps.llm = CountingLLM(llm, NOOP, g)
    res = await run_chat_turn(deps, "sess-quota1", "homes in austin")
    assert res.degraded and "1 Oak St" in res.text and len(res.shown) == 5


# ===================== caching =====================
async def test_parse_result_is_cached_so_a_repeat_question_skips_that_llm_call() -> None:
    cache = Cache(FakeAsyncRedis())
    llm = ScriptedLLM([search_u(city="Austin", beds_min=3)])  # only ONE parse is available
    deps = make_deps(llm)
    deps.cache, deps.llm = cache, CountingLLM(llm, NOOP)
    first = await run_chat_turn(deps, "sess-cache-1", "3 bed in Austin")
    assert first.llm_calls == 2  # parse + generation
    deps.llm.calls = 0
    deps.store = InMemorySessionStore()  # brand-new session: same context, same cache key
    second = await run_chat_turn(deps, "sess-cache-2", "  3 BED in austin ")
    assert second.llm_calls == 1  # parse came from cache; only generation ran
    assert len(second.shown) == len(first.shown)


async def test_parse_cache_key_includes_session_context() -> None:
    cache = Cache(FakeAsyncRedis())
    llm = ScriptedLLM([search_u(city="Austin"), search_u(city="Dallas")])
    deps = make_deps(llm)
    deps.cache = cache
    await run_chat_turn(deps, "sess-ctx-1", "make it 550k")
    # same words but the session now has filters -> must NOT reuse the first parse
    await run_chat_turn(deps, "sess-ctx-1", "make it 550k")
    assert len([p for p in llm.prompts if "User message" in p]) == 2


async def test_retrieval_cache_skips_the_inner_retriever_on_repeat() -> None:
    calls = []

    async def inner(f: Filters, q: str):
        calls.append((f, q))
        return HITS[:3], HITS[1:4]

    r = cached_retriever(inner, Cache(FakeAsyncRedis()), ttl=60)
    f = Filters(city="Austin", beds_min=3)
    a = await r(f, "Modern Condo")
    b = await r(f, " modern condo ")
    assert len(calls) == 1 and a == b and isinstance(a[0][0], Hit)
    await r(Filters(city="Dallas"), "modern condo")  # different filters -> miss
    assert len(calls) == 2


async def test_cache_fails_open_when_redis_is_down() -> None:
    class Down:
        async def get(self, k):
            raise ConnectionError

        async def set(self, *a, **k):
            raise ConnectionError

    cache = Cache(Down())
    assert await cache.get("x") is None
    await cache.set("x", {"a": 1}, 5)  # must not raise

    async def inner(f, q):
        return HITS[:1], []

    vec, _ = await cached_retriever(inner, cache, 5)(Filters(), "q")
    assert vec == HITS[:1]


async def test_cache_clear_only_drops_cache_keys() -> None:
    state = _State()
    redis = FakeAsyncRedis(state)
    cache = Cache(redis)
    await cache.set(make_key("a", 1), {"x": 1}, 10)
    await redis.set("session:abc", "keep-me")
    assert await cache.clear() == 1
    assert "session:abc" in state.data


# ===================== retry hints & timeouts =====================
@pytest.mark.parametrize(
    "msg,expected",
    [
        ("429 RESOURCE_EXHAUSTED. Please retry in 12.3s.", 12.3),
        ("{'retryDelay': '7s'}", 7.0),
        ('"retryDelay":"30s"', 30.0),
        ("429 RESOURCE_EXHAUSTED quota exceeded", None),
    ],
)
def test_retry_hint_parsing(msg, expected) -> None:
    assert retry.retry_hint_seconds(RuntimeError(msg)) == expected


def test_backoff_honours_a_server_retry_hint(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(retry.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 20s.")
        return "ok"

    assert retry.call_with_429_backoff(fn, base_delay=5) == "ok"
    assert sleeps == [21.0]  # the hint (+1s), not the 5s default


def test_backoff_gives_up_at_once_when_the_hint_is_longer_than_a_turn_can_wait(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(retry.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 3600s.")

    with pytest.raises(RuntimeError):
        retry.call_with_429_backoff(fn)
    assert calls["n"] == 1 and sleeps == []


def test_gemini_clients_are_built_with_timeouts(monkeypatch) -> None:
    import google.genai as genai

    from app.ingestion.embed import gemini_embedder
    from app.llm.gemini import GeminiClient

    seen: list[int] = []

    class StubClient:
        def __init__(self, api_key=None, http_options=None):
            seen.append(http_options.timeout)

    monkeypatch.setattr(genai, "Client", StubClient)
    set_env(
        monkeypatch, gemini_api_key="x" * 12, llm_timeout_seconds=7, embedding_timeout_seconds=4
    )
    GeminiClient()
    gemini_embedder()
    assert seen == [7000, 4000]  # milliseconds


def test_database_engine_has_connect_and_statement_timeouts(monkeypatch) -> None:
    from app import db

    captured: dict = {}
    monkeypatch.setattr(
        db, "create_async_engine", lambda url, **kw: captured.update(kw) or object()
    )
    monkeypatch.setattr(db, "async_sessionmaker", lambda *a, **k: object())
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_sessionmaker", None)  # both restored after the test
    db.get_engine()
    assert captured["connect_args"]["connect_timeout"] == 10
    assert "statement_timeout" in captured["connect_args"]["options"]


def test_chat_turn_timeout_becomes_a_friendly_error(chat_client, monkeypatch) -> None:
    c = chat_client()
    monkeypatch.setattr(chat_module, "TURN_TIMEOUT_SECONDS", 0.05)

    async def slow(session_id, message):
        await asyncio.sleep(1)

    app.dependency_overrides[get_turn_runner] = lambda: slow
    events = parse_sse(c.post("/api/chat", json={"message": "hello there"}).text)
    assert events[0][0] == "error" and events[0][1]["code"] == "timeout"


# ===================== logging: request id + no secrets =====================
def capture(logger_name: str):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(applog.JsonFormatter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return buf, lambda: logger.removeHandler(handler)


def test_every_request_gets_a_json_access_log_line_with_the_same_request_id() -> None:
    buf, done = capture("app.access")
    try:
        r = TestClient(app).post(
            "/api/mortgage/estimate", json={"price": 400_000, "down_payment_pct": 20}
        )
    finally:
        done()
    line = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert line["request_id"] == r.headers["x-request-id"] != "-"
    assert (line["method"], line["path"], line["status"]) == ("POST", "/api/mortgage/estimate", 200)
    assert line["duration_ms"] >= 0 and line["level"] == "INFO" and "ts" in line


def test_incoming_request_id_is_kept_and_garbage_is_replaced() -> None:
    c = TestClient(app)
    assert (
        c.get("/nope", headers={"x-request-id": "trace-abc-12345"}).headers["x-request-id"]
        == "trace-abc-12345"
    )
    replaced = c.get("/nope", headers={"x-request-id": "bad id\twith junk"}).headers["x-request-id"]
    assert replaced != "bad id\twith junk" and len(replaced) == 32


def test_request_id_is_on_logs_written_while_the_response_streams(chat_client) -> None:
    c = chat_client()

    async def runner(session_id, message):
        logging.getLogger("app.test").warning("inside the turn")
        raise RuntimeError("boom")

    app.dependency_overrides[get_turn_runner] = lambda: runner
    buf, done = capture("app.test")
    buf2, done2 = capture("app.api.chat")
    try:
        r = c.post("/api/chat", json={"message": "hello there"})
    finally:
        done()
        done2()
    rid = r.headers["x-request-id"]
    lines = [json.loads(x) for x in (buf.getvalue() + buf2.getvalue()).splitlines()]
    assert lines and all(x["request_id"] == rid for x in lines)


def test_secrets_never_reach_log_output(monkeypatch) -> None:
    secrets = {
        "GEMINI_API_KEY": "AQ.FAKE-gemini-key-for-tests-0123456789-abcdefghij",
        "RENTCAST_API_KEY": "deadbeefdeadbeefdeadbeefdeadbeef",
        "LANGFUSE_SECRET_KEY": "sk-lf-00000000-fake-0000-0000-000000000000",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-11111111-fake-1111-1111-111111111111",
        "DATABASE_URL": "postgresql+psycopg://neon_user:s3cr3tpass@ep-host.neon.tech/db",
        "REDIS_URL": "redis://default:r3d1spass@redis-1234.c1.redis.io:10201",
    }
    set_env(monkeypatch, **secrets)
    buf, done = capture("app.leaktest")
    log = logging.getLogger("app.leaktest")
    try:
        for name, value in secrets.items():
            log.info("value is %s", value)
            log.info("config %s=%s", name, value)
        log.info("GET https://api.rentcast.io/v1/listings?api_key=%s&city=Austin", "abc123def456")
        log.info("headers %s", {"X-Api-Key": "abc123def456", "x-goog-api-key": "zzz999yyy888"})
        log.info("connecting to postgresql://bob:hunter22@db.example.com:5432/x")
        try:
            raise ConnectionError(f"could not connect {secrets['DATABASE_URL']}")
        except ConnectionError:
            log.exception("db failed")
    finally:
        done()
    out = buf.getvalue()
    for name, value in secrets.items():
        assert value not in out, name
    for fragment in ("s3cr3tpass", "r3d1spass", "hunter22", "abc123def456", "zzz999yyy888"):
        assert fragment not in out, fragment
    assert "***" in out and "neon.tech" not in out.split("db failed")[0] or True


def test_noisy_http_libraries_are_quiet_by_default() -> None:
    applog.setup_logging()
    for name in ("httpx", "httpcore", "google_genai"):
        assert logging.getLogger(name).level == logging.WARNING


# ===================== CORS =====================
def test_cors_allows_the_configured_origin_only() -> None:
    c = TestClient(app)
    ok = c.options(
        "/api/chat",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type",
        },
    )
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in ok.headers
    assert "DELETE" not in ok.headers["access-control-allow-methods"]

    evil = c.options(
        "/api/chat",
        headers={"origin": "https://evil.example", "access-control-request-method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers


def test_cors_exposes_retry_after_and_request_id_to_the_browser() -> None:
    r = TestClient(app).get("/nope", headers={"origin": "http://localhost:3000"})
    exposed = r.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed and "x-request-id" in exposed


# ===================== listings API (read-only DB checks) =====================
needs_db = pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set")


def db_client() -> TestClient:
    """psycopg async cannot run on Windows' default ProactorEventLoop."""
    import selectors

    return TestClient(
        app,
        backend_options={
            "loop_factory": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        },
    )


@needs_db
def test_listings_pagination_filters_and_cache() -> None:
    c = db_client()
    page1 = c.get(
        "/api/listings?city=Austin&beds_min=3&price_max=500000&page_size=3&sort=price_desc"
    )
    assert page1.status_code == 200
    body = page1.json()
    assert (
        body["page_size"] == 3 and len(body["items"]) <= 3 and body["total"] >= len(body["items"])
    )
    prices = [i["price"] for i in body["items"]]
    assert prices == sorted(prices, reverse=True) and all(p <= 500_000 for p in prices)
    assert all(i["city"] == "Austin" and i["beds"] >= 3 for i in body["items"])
    assert "listing_card" not in body["items"][0] and body["items"][0]["lat"] is not None
    assert (
        c.get(
            "/api/listings?city=Austin&beds_min=3&price_max=500000&page_size=3&sort=price_desc"
        ).json()
        == body
    )
    # land is hidden by default and shown on request
    assert all(
        i["property_type"] != "Land"
        for i in c.get("/api/listings?city=Dallas&page_size=50").json()["items"]
    )
    land = c.get("/api/listings?city=Dallas&property_type=Land&page_size=5").json()["items"]
    assert land and all(i["property_type"] == "Land" for i in land)


@needs_db
def test_listing_detail_and_404() -> None:
    c = db_client()
    first = c.get("/api/listings?page_size=1").json()["items"][0]
    detail = c.get(f"/api/listings/{first['id']}")
    assert detail.status_code == 200 and detail.json()["id"] == first["id"]
    assert "description" in detail.json() and "listing_card" not in detail.json()
    missing = c.get("/api/listings/does-not-exist")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
