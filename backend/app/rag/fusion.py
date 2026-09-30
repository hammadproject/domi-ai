from collections.abc import Sequence

from app.rag.models import Hit

RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[Hit]], k: int = RRF_K
) -> list[tuple[Hit, float]]:
    """Merge ranked lists: score(d) = sum over lists of 1 / (k + rank). Best first."""
    scores: dict[str, float] = {}
    hits: dict[str, Hit] = {}
    for lst in ranked_lists:
        for rank, hit in enumerate(lst, start=1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank)
            hits.setdefault(hit.id, hit)
    order = sorted(scores, key=lambda i: scores[i], reverse=True)
    return [(hits[i], scores[i]) for i in order]
