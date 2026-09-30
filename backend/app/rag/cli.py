"""Try retrieval from the terminal.

One-shot:     python -m app.rag.cli "3 bed house in Austin under 500k"
Conversation: python -m app.rag.cli            (follow-ups keep prior filters; 'quit' exits)
"""

import argparse
import asyncio
import selectors

from app.db import get_engine, get_session
from app.observability.logging import setup_logging
from app.rag.models import Filters, SearchResult
from app.rag.pipeline import db_retriever, search


def _fmt(n: float | None, prefix: str = "") -> str:
    return f"{prefix}{n:,.0f}" if n is not None else "?"


def print_result(res: SearchResult) -> None:
    print(f"\nfilters requested : {res.requested_filters.active()}")
    if res.relaxations:
        print(f"filters applied   : {res.applied_filters.active()}")
    print(f"semantic query    : {res.semantic_query!r}")
    print(f"candidates        : vector={res.n_vector} keyword={res.n_keyword}")
    print(f"\n{res.message}\n")
    for i, r in enumerate(res.results, 1):
        h = r.hit
        beds = f"{h.beds:g}bd" if h.beds is not None else "?bd"
        baths = f"{h.baths:g}ba" if h.baths is not None else "?ba"
        print(
            f"{i}. {h.address} | {_fmt(h.price, '$')} | {beds}/{baths} | "
            f"{_fmt(h.sqft)} sqft | {h.property_type} | score {r.score:.2f}\n   id={h.id}"
        )


async def _run(query: str | None) -> None:
    prior: Filters | None = None
    async for session in get_session():
        retriever = db_retriever(session)
        while True:
            q = query if query is not None else input("\nquery> ").strip()
            if q.lower() in {"quit", "exit", ""}:
                break
            res = await search(q, retriever=retriever, prior=prior)
            print_result(res)
            prior = res.requested_filters
            if query is not None:
                break
    await get_engine().dispose()


def main() -> None:
    setup_logging(level=40)  # errors only; keep CLI output readable
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?")
    a = p.parse_args()
    asyncio.run(
        _run(a.query),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


if __name__ == "__main__":
    main()
