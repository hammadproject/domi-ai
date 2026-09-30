"""Local ONNX cross-encoder rerank (fastembed). No API calls."""

from collections.abc import Callable
from functools import lru_cache

from app.config import get_settings
from app.rag.models import Hit, RankedHit

# (query, documents) -> one relevance score per document, in order
ScoreFn = Callable[[str, list[str]], list[float]]


@lru_cache(maxsize=1)
def _model():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=get_settings().reranker_model)


def cross_encoder_scores(query: str, docs: list[str]) -> list[float]:
    return [float(s) for s in _model().rerank(query, docs)]


def rerank(
    query: str,
    candidates: list[tuple[Hit, float]],
    top_k: int = 5,
    score_fn: ScoreFn = cross_encoder_scores,
) -> list[RankedHit]:
    """Rerank fused candidates (first 20) and return the best top_k."""
    cands = candidates[:20]
    if not cands:
        return []
    docs = [h.listing_card or h.address for h, _ in cands]
    scores = score_fn(query, docs)
    ranked = sorted(zip(cands, scores, strict=True), key=lambda x: x[1], reverse=True)
    return [RankedHit(hit=h, score=s) for (h, _), s in ranked[:top_k]]
