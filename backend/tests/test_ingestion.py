
import httpx
import pytest

from app.ingestion import rentcast
from app.ingestion.embed import embed_texts
from app.ingestion.normalize import normalize_listing

FULL = {
    "id": "123-Main-St,-Austin,-TX-78704",
    "formattedAddress": "123 Main St, Austin, TX 78704",
    "city": "Austin",
    "state": "TX",
    "zipCode": "78704",
    "latitude": 30.25,
    "longitude": -97.76,
    "propertyType": "Single Family",
    "bedrooms": 3,
    "bathrooms": 2,
    "squareFootage": 1800,
    "yearBuilt": 2015,
    "price": 525000,
    "hoa": {"fee": 80},
}


def test_normalize_full_record_and_card() -> None:
    row = normalize_listing(FULL)
    assert row is not None
    assert (row.id, row.price, row.beds, row.hoa_fee) == (FULL["id"], 525000, 3.0, 80.0)
    assert row.listing_card == (
        "3 bed, 2 bath house in Austin TX 78704, $525,000, 1,800 sqft, built 2015, HOA $80/mo."
    )


def test_normalize_missing_fields_do_not_invent_data() -> None:
    row = normalize_listing({"id": "x", "city": "Dallas", "state": "tx", "price": "300000"})
    assert row is not None
    assert row.state == "TX" and row.price == 300000
    assert row.beds is None and row.sqft is None and row.hoa_fee is None
    assert row.listing_card == "Home in Dallas TX, $300,000."


def test_normalize_skips_unusable_records() -> None:
    assert normalize_listing({"city": "Austin", "state": "TX"}) is None
    assert normalize_listing({"id": "x", "state": "TX"}) is None


def test_embeddings_cached_by_content_hash(tmp_path) -> None:
    calls: list[list[str]] = []

    def fake(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[1.0, 0.0] for _ in texts]

    cache = tmp_path / "emb.jsonl"
    kw = {"embedder": fake, "cache_path": cache, "model": "m", "dim": 2}
    vecs, sent = embed_texts(["a", "b", "a"], **kw)
    assert sent == 2 and len(vecs) == 3
    vecs2, sent2 = embed_texts(["a", "b"], **kw)
    assert sent2 == 0 and len(calls) == 1 and vecs2 == vecs[:2]
    _, sent3 = embed_texts(["a", "c"], **kw)
    assert sent3 == 1 and calls[-1] == ["c"]


def test_rentcast_cache_first(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RENTCAST_API_KEY", "k")
    from app.config import get_settings

    get_settings.cache_clear()
    hits = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request)
        assert request.headers["x-api-key"] == "k"
        assert request.url.params["city"] == "Austin"
        assert request.url.params["limit"] == "100"
        return httpx.Response(200, json=[FULL])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    data, live = rentcast.fetch_city("Austin", "TX", raw_dir=tmp_path, client=client)
    assert live and data == [FULL] and len(hits) == 1
    assert len(list(tmp_path.glob("austin_*.json"))) == 1
    assert "city=Austin" in (tmp_path / "live_calls.log").read_text()

    data2, live2 = rentcast.fetch_city("Austin", "TX", raw_dir=tmp_path, client=client)
    assert not live2 and data2 == data and len(hits) == 1
    get_settings.cache_clear()


def test_rentcast_error_writes_no_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RENTCAST_API_KEY", "k")
    from app.config import get_settings

    get_settings.cache_clear()
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"error": "x"}))
    )
    with pytest.raises(httpx.HTTPStatusError):
        rentcast.fetch_city("Dallas", "TX", raw_dir=tmp_path, client=client)
    assert not list(tmp_path.glob("*.json"))
    get_settings.cache_clear()
