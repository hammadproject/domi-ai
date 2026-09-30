"""Endpoints added for the frontend: mortgage defaults/affordability/terms, compare, cities,
and chat context (which listings the user is looking at)."""

import asyncio
import selectors

import pytest
from fastapi.testclient import TestClient

from app.agent.graph import run_chat_turn
from app.agent.understanding import TurnUnderstanding
from app.api.deps import get_turn_runner
from app.config import get_settings
from app.main import app
from app.tools.mortgage import MortgageAssumptions, affordability, compare_terms
from tests.test_agent import HITS, ScriptedLLM, make_deps, parse_sse

client = TestClient(app)


# ---------------- mortgage ----------------
def test_defaults_come_from_settings_not_the_frontend() -> None:
    body = client.get("/api/mortgage/defaults").json()
    a = MortgageAssumptions.from_settings()
    assert (
        body["interest_rate"] == a.interest_rate
        and body["property_tax_rate"] == a.property_tax_rate
    )
    assert body["insurance_annual"] == a.insurance_annual and body["pmi_rate"] == a.pmi_rate
    assert body["pmi_down_payment_threshold_pct"] == 20
    assert {"front_end_dti", "back_end_dti"} <= set(body)


def test_estimate_accepts_assumption_overrides() -> None:
    base = {"price": 500_000, "down_payment_pct": 20}
    default = client.post("/api/mortgage/estimate", json=base).json()
    custom = client.post(
        "/api/mortgage/estimate",
        json={**base, "interest_rate": 6.0, "property_tax_rate": 1.2, "insurance_annual": 1200},
    ).json()
    assert custom["interest_rate"] == 6.0 and custom["principal_interest"] == pytest.approx(2398.20)
    assert custom["property_tax"] == 500.0 and custom["insurance"] == 100.0
    assert custom["total_monthly"] != default["total_monthly"]


def test_estimate_pmi_override_and_threshold() -> None:
    low = client.post(
        "/api/mortgage/estimate",
        json={"price": 400_000, "down_payment_pct": 5, "pmi_rate": 1.0},
    ).json()
    assert low["pmi_applies"] and low["pmi"] == pytest.approx(380_000 * 1.0 / 100 / 12, abs=0.01)
    none = client.post(
        "/api/mortgage/estimate", json={"price": 400_000, "down_payment_pct": 20}
    ).json()
    assert not none["pmi_applies"] and none["pmi"] == 0


def test_compare_terms_endpoint_matches_the_tool() -> None:
    r = client.post(
        "/api/mortgage/compare-terms", json={"price": 489_000, "down_payment_pct": 20}
    ).json()
    expected = compare_terms(
        489_000, down_payment_pct=20, assumptions=MortgageAssumptions.from_settings()
    )
    assert r["shorter"]["term_years"] == 15 and r["longer"]["term_years"] == 30
    assert r["shorter"]["total_monthly"] == expected.shorter.total_monthly
    assert r["monthly_difference"] > 0 and r["interest_saved_by_shorter"] > 0


def test_affordability_endpoint_matches_the_tool() -> None:
    body = {"annual_income": 120_000, "monthly_debts": 500, "down_payment": 80_000}
    r = client.post("/api/mortgage/affordability", json=body).json()
    e = affordability(
        annual_income=120_000, monthly_debts=500, down_payment=80_000,
        assumptions=MortgageAssumptions.from_settings(),
    )  # fmt: skip
    assert r["affordable"] and r["max_home_price"] == e.max_home_price
    assert r["binding_limit"] in {"front_end_dti", "back_end_dti"}
    # raising the DTI ceiling can only raise (never lower) what you can afford
    looser = client.post(
        "/api/mortgage/affordability", json={**body, "back_end_dti": 0.45, "front_end_dti": 0.35}
    ).json()
    assert looser["max_home_price"] > r["max_home_price"]


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/mortgage/compare-terms", {"price": 400_000}),
        ("/api/mortgage/compare-terms", {"price": 400_000, "down_payment_pct": 20, "short_term_years": 30, "long_term_years": 30}),
        ("/api/mortgage/affordability", {"annual_income": 0, "down_payment": 1}),
        ("/api/mortgage/affordability", {"annual_income": 100_000, "down_payment": -5}),
        ("/api/mortgage/affordability", {"annual_income": 100_000, "down_payment": 1, "back_end_dti": 1.5}),
        ("/api/mortgage/estimate", {"price": 100_000, "down_payment_pct": 10, "interest_rate": 99}),
    ],
)  # fmt: skip
def test_new_mortgage_endpoints_validate_input(path, body) -> None:
    r = client.post(path, json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_affordability_not_affordable_is_a_result_not_an_error() -> None:
    r = client.post(
        "/api/mortgage/affordability",
        json={"annual_income": 50_000, "monthly_debts": 5_000, "down_payment": 1_000},
    )
    assert r.status_code == 200 and r.json()["affordable"] is False


# ---------------- chat context ----------------
def test_chat_context_ids_are_validated(monkeypatch) -> None:
    captured = {}

    async def runner(session_id, message, context_ids=(), filters=None):
        captured["ids"] = list(context_ids)
        deps = make_deps(ScriptedLLM([TurnUnderstanding(intent="smalltalk")]))
        return await run_chat_turn(deps, session_id, message)

    app.dependency_overrides[get_turn_runner] = lambda: runner
    ok = client.post("/api/chat", json={"message": "hello", "context_listing_ids": ["a", "b"]})
    assert ok.status_code == 200 and captured["ids"] == ["a", "b"]
    for bad in (["a", "b", "c", "d"], [""], ["x" * 201], "not-a-list"):
        r = client.post("/api/chat", json={"message": "hello", "context_listing_ids": bad})
        assert r.status_code == 422, bad


async def test_context_listings_become_what_the_user_is_looking_at() -> None:
    """'compare them' and 'payment for the first one' resolve against the context listings."""
    fetched: list[list[str]] = []

    async def fetcher(ids):
        fetched.append(ids)
        return [h for i in ids for h in HITS if h.id == i]

    llm = ScriptedLLM(
        [
            TurnUnderstanding(intent="compare", listing_positions=[1, 2]),
            TurnUnderstanding(intent="mortgage", listing_positions=[2]),
        ]
    )
    deps = make_deps(llm)
    deps.hits_fetcher = fetcher
    cmp_ = await run_chat_turn(deps, "sess-ctx-a1", "compare these", ["h3", "h1"])
    assert fetched == [["h3", "h1"]]
    assert "3 Oak St" in cmp_.text and "1 Oak St" in cmp_.text  # order preserved from the context
    pay = await run_chat_turn(deps, "sess-ctx-a1", "payment for the second one")
    assert "1 Oak St" in pay.text  # position 2 of [h3, h1]


async def test_unknown_context_ids_leave_the_session_unchanged() -> None:
    async def fetcher(ids):
        return []

    llm = ScriptedLLM([TurnUnderstanding(intent="compare", listing_positions=[1, 2])])
    deps = make_deps(llm)
    deps.hits_fetcher = fetcher
    res = await run_chat_turn(deps, "sess-ctx-b2", "compare them", ["nope"])
    assert "two or three" in res.text


def test_sse_passes_context_ids_to_the_turn(monkeypatch) -> None:
    seen = {}

    async def runner(session_id, message, context_ids=(), filters=None):
        seen["ids"] = list(context_ids)
        deps = make_deps(ScriptedLLM([TurnUnderstanding(intent="smalltalk")]))
        return await run_chat_turn(deps, session_id, message)

    app.dependency_overrides[get_turn_runner] = lambda: runner
    r = client.post("/api/chat", json={"message": "hi there", "context_listing_ids": ["h1"]})
    assert parse_sse(r.text)[-1][0] == "done" and seen["ids"] == ["h1"]


# ---------------- database-backed (read-only) ----------------
needs_db = pytest.mark.skipif(not get_settings().database_url, reason="DATABASE_URL not set")


def db_client() -> TestClient:
    return TestClient(
        app,
        backend_options={
            "loop_factory": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        },
    )


@needs_db
def test_cities_endpoint_reports_real_homes_only() -> None:
    r = db_client().get("/api/cities")
    assert r.status_code == 200
    cities = {c["city"]: c for c in r.json()}
    assert {"Austin", "Dallas", "Phoenix"} <= set(cities)
    austin = cities["Austin"]
    assert (
        austin["state"] == "TX" and 0 < austin["listing_count"] < 100
    )  # Land excluded (100 total)
    assert austin["min_price"] <= austin["median_price"] <= austin["max_price"]
    assert 29 < austin["center_lat"] < 31 and -99 < austin["center_lng"] < -96


@needs_db
def test_compare_endpoint_with_real_listings() -> None:
    c = db_client()
    items = c.get("/api/listings?city=Austin&beds_min=3&page_size=3&sort=price_asc").json()["items"]
    ids = [i["id"] for i in items]
    r = c.post(
        "/api/compare",
        json={"listing_ids": ids, "down_payment_pct": 10, "interest_rate": 6.5, "term_years": 15},
    )
    assert r.status_code == 200
    body = r.json()
    assert [x["id"] for x in body["listings"]] == ids
    assert body["down_payment_pct"] == 10 and body["term_years"] == 15
    first = body["listings"][0]
    assert first["city"] == "Austin" and first["est_monthly_payment"] > 0
    assert any("Lowest list price" in p for p in first["pros"])  # cheapest is first (price_asc)
    assert "15-year" in body["payment_note"]


@needs_db
def test_compare_endpoint_errors() -> None:
    c = db_client()
    ids = [i["id"] for i in c.get("/api/listings?page_size=2").json()["items"]]
    assert c.post("/api/compare", json={"listing_ids": ids[:1]}).status_code == 422
    assert c.post("/api/compare", json={"listing_ids": [ids[0], ids[0]]}).status_code == 422
    missing = c.post("/api/compare", json={"listing_ids": [ids[0], "no-such-listing"]})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


# ---------------- page filters override session memory ----------------
async def test_page_filters_replace_remembered_filters() -> None:
    from app.rag.models import Filters

    seen: list[Filters] = []
    llm = ScriptedLLM(
        [
            TurnUnderstanding(intent="search", filters=Filters(city="Dallas", price_max=350_000)),
            TurnUnderstanding(intent="search", filters=Filters(price_max=550_000)),
        ]
    )
    deps = make_deps(llm, seen=seen)
    await run_chat_turn(deps, "sess-ui-1", "dallas under 350k")
    assert seen[-1].city == "Dallas"
    # the person then changed the page to Austin / 3+ beds; "raise it to 550k" must build on THAT
    await run_chat_turn(
        deps, "sess-ui-1", "raise it to 550k", filters=Filters(city="Austin", beds_min=3)
    )
    f = seen[-1]
    assert (f.city, f.beds_min, f.price_max) == ("Austin", 3, 550_000)


def test_chat_accepts_and_validates_page_filters() -> None:
    captured = {}

    async def runner(session_id, message, context_ids=(), filters=None):
        captured["filters"] = filters
        deps = make_deps(ScriptedLLM([TurnUnderstanding(intent="smalltalk")]))
        return await run_chat_turn(deps, session_id, message)

    app.dependency_overrides[get_turn_runner] = lambda: runner
    ok = client.post(
        "/api/chat", json={"message": "hello", "filters": {"city": "Austin", "beds_min": 3}}
    )
    assert ok.status_code == 200
    assert captured["filters"].city == "Austin" and captured["filters"].beds_min == 3
    bad = client.post(
        "/api/chat", json={"message": "hello", "filters": {"property_type": "Castle"}}
    )
    assert bad.status_code == 422
