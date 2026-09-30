"""Gemini embeddings with an on-disk content-hash cache (zero quota on re-runs)."""

import hashlib
import json
import logging
import math
import time
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.llm.retry import call_with_429_backoff

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parents[3] / "data" / "cache" / "embeddings.jsonl"
BATCH_SIZE = 50
Embedder = Callable[[list[str]], list[list[float]]]


def content_hash(text: str, model: str, dim: int) -> str:
    return hashlib.sha256(f"{model}|{dim}|RETRIEVAL_DOCUMENT|{text}".encode()).hexdigest()


def l2_normalize(v: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def _load_cache(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    out: dict[str, list[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["h"]] = rec["v"]
    return out


def gemini_embedder(task_type: str = "RETRIEVAL_DOCUMENT") -> Embedder:
    from google import genai
    from google.genai import types

    s = get_settings()
    client = genai.Client(
        api_key=s.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(timeout=s.embedding_timeout_seconds * 1000),  # ms
    )

    def embed(texts: list[str]) -> list[list[float]]:
        resp = call_with_429_backoff(
            lambda: client.models.embed_content(
                model=s.embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=s.embedding_dim
                ),
            )
        )
        return [l2_normalize(e.values) for e in resp.embeddings]

    return embed


@lru_cache(maxsize=256)
def embed_query(text: str) -> tuple[float, ...]:
    """Embed a user query (RETRIEVAL_QUERY). Memoized in-process to save quota."""
    return tuple(gemini_embedder("RETRIEVAL_QUERY")([text])[0])


def embed_texts(
    texts: list[str],
    *,
    embedder: Embedder | None = None,
    cache_path: Path = CACHE_PATH,
    model: str | None = None,
    dim: int | None = None,
) -> tuple[list[list[float]], int]:
    """Return (vectors aligned with texts, number of texts sent to the API)."""
    s = get_settings()
    model, dim = model or s.embedding_model, dim or s.embedding_dim
    cache = _load_cache(cache_path)
    hashes = [content_hash(t, model, dim) for t in texts]
    missing = list(dict.fromkeys(h for h in hashes if h not in cache))
    by_hash = dict(zip(hashes, texts, strict=True))

    if missing:
        embedder = embedder or gemini_embedder()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("a", encoding="utf-8") as f:
            for i in range(0, len(missing), BATCH_SIZE):
                batch = missing[i : i + BATCH_SIZE]
                vecs = embedder([by_hash[h] for h in batch])
                for h, v in zip(batch, vecs, strict=True):
                    cache[h] = v
                    f.write(json.dumps({"h": h, "v": v}) + "\n")
                log.info("embedded %d/%d new listing cards", i + len(batch), len(missing))
                if i + BATCH_SIZE < len(missing):
                    time.sleep(2)  # stay polite to free-tier per-minute limits
    return [cache[h] for h in hashes], len(missing)
