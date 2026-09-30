"""RentCast sale-listings client. Cache-first: a live call is made only if no
cached response exists for the city in data/raw/. Every live call is logged."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

BASE_URL = "https://api.rentcast.io/v1/listings/sale"
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
CALL_LOG = RAW_DIR / "live_calls.log"


def _slug(city: str) -> str:
    return city.strip().lower().replace(" ", "_")


def find_cache(city: str, raw_dir: Path = RAW_DIR) -> Path | None:
    """Newest cached response for the city (any date), or None."""
    matches = sorted(raw_dir.glob(f"{_slug(city)}_*.json"))
    return matches[-1] if matches else None


def fetch_city(
    city: str,
    state: str,
    *,
    limit: int = 100,
    raw_dir: Path = RAW_DIR,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Return (listings, was_live_call)."""
    cached = find_cache(city, raw_dir)
    if cached is not None:
        log.info("rentcast cache hit: %s", cached.name)
        return json.loads(cached.read_text(encoding="utf-8")), False

    key = get_settings().rentcast_api_key.get_secret_value()
    if not key:
        raise RuntimeError("RENTCAST_API_KEY is not set and no cache exists")

    params = {"city": city, "state": state, "status": "Active", "limit": limit}
    log.warning("rentcast LIVE call: city=%s state=%s limit=%s", city, state, limit)
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.get(BASE_URL, params=params, headers={"X-Api-Key": key})
        if resp.is_error:
            log.error("rentcast error %s: %s", resp.status_code, resp.text[:300])
            resp.raise_for_status()
        data = resp.json()
    finally:
        if own:
            client.close()

    raw_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    path = raw_dir / f"{_slug(city)}_{today}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with (raw_dir / CALL_LOG.name).open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(UTC).isoformat()} city={city} state={state} n={len(data)}\n")
    return data, True
