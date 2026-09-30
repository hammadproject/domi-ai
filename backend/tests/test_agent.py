import json

import pytest
from fastapi.testclient import TestClient

from app.agent.generate import GroundedAnswer
from app.agent.graph import AgentDeps, run_chat_turn
from app.agent.memory import InMemorySessionStore, RedisSessionStore, SessionState
from app.agent.understanding import MortgageArgs, TurnUnderstanding
from app.api.deps import get_turn_runner
from app.guardrails.input_guard import Classification
from app.llm.counting import CountingLLM
from app.main import app
from app.observability.tracing import NOOP, Tracer
from app.rag.models import Filters, Hit

PRICES = [310_000, 345_000, 410_000, 480_000, 520_000, 540_000]
HITS = [
    Hit(
        id=f"h{i}", address=f"{i} Oak St", city="Austin", state="TX", price=p,
        beds=3, baths=2, sqft=1500 + 100 * i, year_built=2000 + i, hoa_fee=(50 if i == 1 else None),
        property_type="Single Family", lat=30.2 + i / 100, lng=-97.7,
    )
    for i, p in enumerate(PRICES, 1)
]  # fmt: skip


class ScriptedLLM:
    """Returns queued TurnUnderstanding objects; answers generation from the prompt."""

    def __init__(self, understandings=(), answer=None, fail_generation=False) -> None:
        self.queue = list(understandings)
        self.answer = answer
        self.fail_generation = fail_generation
        self.prompts: list[str] = []

    def generate_structured(self, prompt, schema, *, system=None):
        self.prompts.append(prompt)
        if schema is TurnUnderstanding:
            return self.queue.pop(0)
        if schema is GroundedAnswer:
            if self.fail_generation:
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            ids = [h["id"] for h in json.loads(prompt.split("Listing records:\n")[1])]
            return self.answer or GroundedAnswer(answer="Here are your homes.", listing_ids=ids)
        if schema is Classification:
            return Classification(steering=False, category="none", reason="ok")
        raise AssertionError(schema)


def make_deps(llm, store=None, seen=None) -> AgentDeps:
    async def retriever(f: Filters, q: str):
        if seen is not None:
            seen.append(f)
        ok = [
            h
            for h in HITS
            if (f.price_max is None or h.price <= f.price_max)
            and (f.beds_min is None or h.beds >= f.beds_min)
        ]
        return ok, []

    return AgentDeps(
        llm=CountingLLM(llm, NOOP),
        store=store or InMemorySessionStore(),
        tracer=NOOP,
        retriever=retriever,
        score_fn=lambda q, docs: [-i for i in range(len(docs))],  # keep retrieval order
    )


def search_u(**filters) -> TurnUnderstanding:
    return TurnUnderstanding(intent="search", filters=Filters(**filters))


# ---------------- the headline multi-turn flow ----------------
async def test_multi_turn_search_refine_then_payment_for_first() -> None:
    seen: list[Filters] = []
    llm = ScriptedLLM(
        [
            search_u(city="Austin", state="TX", beds_min=3, price_max=500_000),
            search_u(price_max=550_000),
            TurnUnderstanding(intent="mortgage", listing_positions=[1]),
        ]
    )
    deps = make_deps(llm, seen=seen)

    t1 = await run_chat_turn(deps, "sess-1234", "3 bed in Austin under 500k")
    assert t1.intent == "search" and t1.llm_calls == 2
    assert [h.price for _, h in t1.shown] == [310_000, 345_000, 410_000, 480_000]

    deps.llm.calls = 0
    t2 = await run_chat_turn(deps, "sess-1234", "make it 550k")
    f = seen[-1]  # the retriever saw the MERGED filters
    assert (f.city, f.state, f.beds_min, f.price_max) == ("Austin", "TX", 3, 550_000)
    assert len(t2.shown) == 5 and t2.llm_calls == 2  # 2 calls per normal turn

    deps.llm.calls = 0
    t3 = await run_chat_turn(deps, "sess-1234", "monthly payment for the first one")
    assert t3.intent == "mortgage" and t3.llm_calls == 1  # deterministic tool: no 2nd call
    assert "1 Oak St" in t3.text and "$310,000" in t3.text
    assert "20% down" in t3.text and "HOA $50.00" in t3.text  # first listing's HOA used
    assert "not a loan offer" in t3.text.lower()
    assert [h.id for _, h in t3.shown] == ["h1"]


async def test_follow_up_without_context_keeps_no_stale_filters_for_new_session() -> None:
    seen: list[Filters] = []
    llm = ScriptedLLM([search_u(price_max=550_000)])
    await run_chat_turn(make_deps(llm, seen=seen), "other-session", "under 550k")
    assert seen[-1].city is None  # nothing leaked from another session


async def test_mortgage_numbers_match_the_calculator_not_the_llm() -> None:
    from app.tools.mortgage import MortgageAssumptions, estimate_payment

    llm = ScriptedLLM(
        [
            TurnUnderstanding(
                intent="mortgage", mortgage=MortgageArgs(price=400_000, down_payment_pct=10)
            )
        ]
    )
    res = await run_chat_turn(make_deps(llm), "sess-2345", "payment on 400k with 10% down")
    expected = estimate_payment(
        400_000, down_payment_pct=10, assumptions=MortgageAssumptions.from_settings()
    )
    assert f"${expected.total_monthly:,.2f}" in res.text and "PMI" in res.text


async def test_mortgage_asks_which_home_when_unclear() -> None:
    llm = ScriptedLLM([TurnUnderstanding(intent="mortgage")])
    res = await run_chat_turn(make_deps(llm), "sess-3456", "what would my payment be")
    assert "Which home" in res.text and res.llm_calls == 1


async def test_affordability_needs_income_and_down_payment() -> None:
    u = TurnUnderstanding(intent="mortgage", mortgage=MortgageArgs(kind="affordability"))
    res = await run_chat_turn(make_deps(ScriptedLLM([u])), "sess-4567", "how much can I afford")
    assert "annual income" in res.text

    u2 = TurnUnderstanding(
        intent="mortgage",
        mortgage=MortgageArgs(kind="affordability", annual_income=120_000, down_payment=60_000),
    )
    res2 = await run_chat_turn(
        make_deps(ScriptedLLM([u2])), "sess-4568", "afford on 120k, 60k down"
    )
    assert "could afford a home up to about" in res2.text


async def test_compare_two_shown_listings_and_single_asks_for_more() -> None:
    llm = ScriptedLLM(
        [
            search_u(city="Austin", beds_min=3),
            TurnUnderstanding(intent="compare", listing_positions=[1, 2]),
            TurnUnderstanding(intent="compare", listing_positions=[1]),
        ]
    )
    deps = make_deps(llm)
    await run_chat_turn(deps, "sess-5678", "3 bed in austin")
    cmp_ = await run_chat_turn(deps, "sess-5678", "compare the first two")
    assert "1 Oak St" in cmp_.text and "2 Oak St" in cmp_.text and "Lowest list price" in cmp_.text
    assert [r for r, _ in cmp_.shown] == [1, 2]
    one = await run_chat_turn(deps, "sess-5678", "compare the first")
    assert "two or three" in one.text


async def test_smalltalk_costs_one_call() -> None:
    llm = ScriptedLLM([TurnUnderstanding(intent="smalltalk")])
    res = await run_chat_turn(make_deps(llm), "sess-6789", "hello!")
    assert res.llm_calls == 1 and "Domi" in res.text and res.shown == []


# ---------------- guardrails inside the graph ----------------
async def test_fair_housing_refusal_makes_zero_llm_calls_and_no_search() -> None:
    seen: list[Filters] = []
    llm = ScriptedLLM()
    res = await run_chat_turn(
        make_deps(llm, seen=seen), "sess-7890", "Best neighborhood in Austin for white families?"
    )
    assert res.refused and res.llm_calls == 0 and seen == [] and res.shown == []
    assert "Fair Housing" in res.text and res.guard_categories == ["steering"]


async def test_output_guard_strips_subjective_claims_from_generated_answer() -> None:
    bad = GroundedAnswer(
        answer="1 Oak St is $310,000 with 3 beds. It is in a safe, family-friendly neighborhood.",
        listing_ids=["h1"],
    )
    llm = ScriptedLLM([search_u(city="Austin")], answer=bad)
    res = await run_chat_turn(make_deps(llm), "sess-8901", "homes in austin")
    assert "1 Oak St is $310,000 with 3 beds." in res.text
    assert "safe" not in res.text and "family-friendly" not in res.text
    assert res.guard_categories  # the trigger is reported


async def test_hallucinated_listing_ids_are_dropped() -> None:
    bad = GroundedAnswer(answer="Two homes.", listing_ids=["h1", "made-up-id"])
    llm = ScriptedLLM([search_u(city="Austin")], answer=bad)
    res = await run_chat_turn(make_deps(llm), "sess-9012", "homes in austin")
    assert [h.id for _, h in res.shown] == ["h1"]


async def test_generation_failure_degrades_to_deterministic_answer() -> None:
    llm = ScriptedLLM([search_u(city="Austin")], fail_generation=True)
    res = await run_chat_turn(make_deps(llm), "sess-0123", "homes in austin")
    assert res.degraded and "1 Oak St" in res.text and len(res.shown) == 5


async def test_no_results_is_honest_and_skips_generation() -> None:
    llm = ScriptedLLM([search_u(city="Austin", price_max=1_000)])
    res = await run_chat_turn(make_deps(llm), "sess-1357", "homes under 1k")
    assert res.shown == [] and "No listings match" in res.text and res.llm_calls == 1


# ---------------- memory ----------------
async def test_session_memory_persists_filters_results_and_history() -> None:
    store = InMemorySessionStore()
    llm = ScriptedLLM([search_u(city="Austin", beds_min=3, price_max=500_000)])
    await run_chat_turn(make_deps(llm, store=store), "sess-2468", "3 bed in Austin under 500k")
    s = await store.load("sess-2468")
    assert s.filters.price_max == 500_000 and s.filters.city == "Austin"
    assert [h.id for h in s.last_results][0] == "h1" and s.last_results[0].listing_card is None
    assert [t.role for t in s.history] == ["user", "assistant"]


async def test_history_is_capped() -> None:
    s = SessionState(session_id="x" * 8)
    for i in range(10):
        s.add_turn(f"u{i}", f"a{i}")
    assert len(s.history) == 6 and s.history[-1].content == "a9"


class FakeRedis:
    def __init__(self) -> None:
        self.data, self.ttls = {}, {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key], self.ttls[key] = value, ex


async def test_redis_store_uses_ttl_and_survives_failures() -> None:
    r = FakeRedis()
    store = RedisSessionStore(r, ttl=123)
    s = SessionState(session_id="abcdefgh", filters=Filters(city="Dallas"))
    await store.save(s)
    assert r.ttls["session:abcdefgh"] == 123
    assert (await store.load("abcdefgh")).filters.city == "Dallas"

    class Broken:
        async def get(self, key):
            raise ConnectionError

        async def set(self, *a, **k):
            raise ConnectionError

    broken = RedisSessionStore(Broken())
    await broken.save(s)  # must not raise
    assert (await broken.load("abcdefgh")).filters.city is None  # starts fresh


# ---------------- tracing wrapper ----------------
def test_tracer_is_a_silent_noop_without_keys(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")  # env overrides .env, even when keys exist
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    get_settings.cache_clear()
    try:
        t = Tracer.from_settings()
    finally:
        get_settings.cache_clear()
    assert not t.enabled
    with t.trace("chat", session_id="s", input={}) as tr, t.span("n") as sp:
        sp.update(output=1)
        tr.update(output=2)
    assert tr.trace_id is None


def test_tracer_creates_a_trace_with_node_spans_and_survives_client_errors() -> None:
    events: list[tuple] = []

    class Obs:
        def __init__(self, name):
            self.name = name

        def update(self, **kw):
            events.append(("update", self.name))

        def __enter__(self):
            events.append(("enter", self.name))
            return self

        def __exit__(self, *a):
            events.append(("exit", self.name))

    class Client:
        def start_as_current_observation(self, *, name, **kw):
            return Obs(name)

        def get_current_trace_id(self):
            return "trace123"

        def get_trace_url(self, trace_id):
            return f"https://lf/{trace_id}"

        def flush(self):
            events.append(("flush",))

    t = Tracer(Client())
    with t.trace("chat", session_id="s1") as tr:
        with t.span("input_guard"):
            pass
    assert tr.trace_id == "trace123" and tr.url == "https://lf/trace123"
    names = [e[1] for e in events if e[0] == "enter"]
    assert names == ["chat", "input_guard"]
    t.flush()
    assert ("flush",) in events


async def test_graph_emits_one_span_per_node_inside_one_trace() -> None:
    entered: list[str] = []

    class Obs:
        def update(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class Client:
        def start_as_current_observation(self, *, name, **kw):
            entered.append(name)
            return Obs()

        def get_current_trace_id(self):
            return "t1"

        def get_trace_url(self, trace_id):
            return "u"

        def flush(self):
            pass

    llm = ScriptedLLM([search_u(city="Austin")])
    deps = make_deps(llm)
    deps.tracer = Tracer(Client())
    await run_chat_turn(deps, "sess-trace1", "homes in austin")
    assert entered[0] == "chat" and entered.count("chat") == 1
    for node in ("input_guard", "understand", "search", "generate", "output_guard", "finalize"):
        assert node in entered, node


# ---------------- HTTP API ----------------
def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        event, data = block.split("\n", 1)
        out.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


@pytest.fixture
def client():
    llm_holder: dict = {}

    def factory(llm):
        deps = make_deps(llm)

        async def runner(session_id, message, context_ids=()):
            return await run_chat_turn(deps, session_id, message, context_ids)

        app.dependency_overrides[get_turn_runner] = lambda: runner
        llm_holder["deps"] = deps
        return TestClient(app)

    yield factory
    app.dependency_overrides.clear()


def test_chat_sse_event_sequence_and_payload(client) -> None:
    c = client(ScriptedLLM([search_u(city="Austin", beds_min=3, price_max=500_000)]))
    r = c.post(
        "/api/chat", json={"message": "3 bed in Austin under 500k", "session_id": "abcd1234"}
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    kinds = [k for k, _ in events]
    assert kinds[0] == "listings" and kinds[-1] == "done" and set(kinds[1:-1]) == {"token"}
    listings = events[0][1]
    assert listings["highlight_ids"] == [d["id"] for d in listings["listings"]]
    first = listings["listings"][0]
    assert first["rank"] == 1 and {"lat", "lng", "price", "address"} <= set(first)
    assert "listing_card" not in first
    streamed = "".join(d["text"] for k, d in events if k == "token")
    assert streamed == "Here are your homes."
    done = events[-1][1]
    assert (
        done["session_id"] == "abcd1234" and done["llm_calls"] == 2 and done["intent"] == "search"
    )


def test_chat_generates_session_id_when_missing(client) -> None:
    c = client(ScriptedLLM([TurnUnderstanding(intent="smalltalk")]))
    done = parse_sse(c.post("/api/chat", json={"message": "hi"}).text)[-1][1]
    assert len(done["session_id"]) == 32


def test_chat_emits_error_event_not_a_stack_trace(client) -> None:
    c = client(ScriptedLLM([]))  # empty queue -> IndexError inside the turn

    async def boom(session_id, message, context_ids=()):
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_turn_runner] = lambda: boom
    r = c.post("/api/chat", json={"message": "hello there"})
    events = parse_sse(r.text)
    msg = "Something went wrong. Please try again shortly."
    assert events == [("error", {"code": "internal", "message": msg})]
    assert "secret" not in r.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 1001},
        {"message": "hi", "session_id": "bad id!"},
        {"message": "hi", "session_id": "short"},
        {"message": 123},
    ],
)
def test_chat_validation_returns_422(client, body) -> None:
    c = client(ScriptedLLM([]))
    assert c.post("/api/chat", json=body).status_code == 422


def test_mortgage_endpoint_matches_calculator() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/mortgage/estimate",
        json={"price": 500_000, "down_payment_pct": 20, "hoa_monthly": 100, "interest_rate": 6.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["loan_amount"] == 400_000 and body["principal_interest"] == pytest.approx(2398.20)
    assert body["pmi"] == 0 and body["hoa"] == 100


@pytest.mark.parametrize(
    "body",
    [
        {"price": 500_000},  # no down payment
        {"price": 500_000, "down_payment": 1, "down_payment_pct": 1},  # both
        {"price": -5, "down_payment_pct": 10},
        {"price": 500_000, "down_payment": 600_000},  # more than price -> calculator ValueError
        {"price": 500_000, "down_payment_pct": 120},
        {"price": 500_000, "down_payment_pct": 10, "term_years": 0},
    ],
)
def test_mortgage_endpoint_validation_422(body) -> None:
    assert TestClient(app).post("/api/mortgage/estimate", json=body).status_code == 422
