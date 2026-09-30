"""CLI: python -m app.ingestion.run [--city Austin --state TX]  (default: all 3 cities)"""

import argparse
import asyncio
import logging
import selectors

from sqlalchemy import func, select

from app.db import get_engine, get_session
from app.ingestion.embed import embed_texts
from app.ingestion.load import upsert_listings
from app.ingestion.normalize import normalize_listing
from app.ingestion.rentcast import fetch_city
from app.models import Listing
from app.observability.logging import setup_logging

log = logging.getLogger("ingestion")
DEFAULT_CITIES = [("Austin", "TX"), ("Dallas", "TX"), ("Phoenix", "AZ")]


async def ingest(cities: list[tuple[str, str]]) -> dict[str, int]:
    stats = {"live_rentcast_calls": 0, "embedding_texts_sent": 0, "upserted": 0, "skipped": 0}
    async for session in get_session():
        for city, state in cities:
            raw, live = fetch_city(city, state)
            stats["live_rentcast_calls"] += int(live)
            rows = [r for r in (normalize_listing(x) for x in raw) if r is not None]
            stats["skipped"] += len(raw) - len(rows)
            vectors, sent = embed_texts([r.listing_card for r in rows])
            stats["embedding_texts_sent"] += sent
            n = await upsert_listings(session, rows, vectors)
            stats["upserted"] += n
            log.info("%s %s: %d listings (live=%s, new embeddings=%d)", city, state, n, live, sent)
        counts = await session.execute(
            select(Listing.city, func.count()).group_by(Listing.city).order_by(Listing.city)
        )
        for city, n in counts:
            log.info("in DB: %s = %d", city, n)
    await get_engine().dispose()
    return stats


def main() -> None:
    setup_logging()
    p = argparse.ArgumentParser()
    p.add_argument("--city")
    p.add_argument("--state")
    a = p.parse_args()
    cities = [(a.city, a.state)] if a.city and a.state else DEFAULT_CITIES
    stats = asyncio.run(
        ingest(cities),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    log.info("done: %s", stats)


if __name__ == "__main__":
    main()
