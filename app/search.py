"""Layered Search — L1(FTS5) + L2(keywords) + L3(summary match).

Three-tier recall with progressive scoring:
  L1: FTS5 full-text on messages → bm25 score
  L2: jieba keyword matching on keywords table → overlap count
  L3: Summary text containment → bonus multiplier
"""

from app.memory import MemoryRepo


def layered_search(db, query: str, top_n: int = 5) -> list[dict]:
    """Execute 3-layer search and return ranked results.

    Each hit: {session_id, summary, keywords, score, matched_in: [L1|L2|L3]}
    """
    repo = MemoryRepo(db)

    # L1 + L2 from MemoryRepo (already implements dual-recall)
    base_hits = repo.query(query, top_n=top_n * 2)

    # L3: summary containment bonus
    query_lower = query.lower()
    for h in base_hits:
        summary_lower = h.summary.lower()
        if query_lower in summary_lower:
            h.score += 0.2  # exact substring match bonus
        elif any(word in summary_lower for word in query_lower.split() if len(word) >= 2):
            h.score += 0.1  # partial word match

    # Re-sort
    base_hits.sort(key=lambda h: h.score, reverse=True)
    top = base_hits[:top_n]

    return [
        {
            "session_id": h.session_id,
            "summary": h.summary,
            "keywords": h.keywords,
            "score": round(h.score, 3),
            "matched_in": _detect_layers(h, query),
        }
        for h in top
    ]


def _detect_layers(hit, query: str) -> list[str]:
    """Determine which layers contributed to this hit."""
    layers = []
    if hit.source in ("fts", "both"):
        layers.append("L1")
    if hit.source in ("keywords", "both"):
        layers.append("L2")
    query_lower = query.lower()
    if query_lower in hit.summary.lower() or any(
        w in hit.summary.lower() for w in query_lower.split() if len(w) >= 2
    ):
        layers.append("L3")
    return layers
