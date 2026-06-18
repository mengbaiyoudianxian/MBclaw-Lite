"""L1→L2→L3 layered memory search for real-time context prefetch."""

import json
from sqlalchemy.orm import Session as DBSession

from app.models.summary import Summary
from app.models.keyword import Keyword
from app.models.classification_node import ClassificationNode
from app.services.vector_store import search_similar


def _keyword_match(db: DBSession, project_id: int, query: str, limit: int = 10) -> list[dict]:
    """L1: fast keyword match from keyword table (<10ms)."""
    words = [w.strip() for w in query.split() if len(w.strip()) > 1]
    if not words:
        return []
    results = []
    seen = set()
    for w in words:
        rows = (
            db.query(Keyword)
            .filter(Keyword.project_id == project_id, Keyword.keyword.like(f"%{w}%"))
            .order_by(Keyword.weight.desc())
            .limit(limit)
            .all()
        )
        for kw in rows:
            if kw.session_id not in seen:
                seen.add(kw.session_id)
                summary = db.query(Summary).filter(Summary.session_id == kw.session_id).first()
                results.append({
                    "source": "L1_keyword",
                    "session_id": kw.session_id,
                    "keyword": kw.keyword,
                    "summary": summary.topic if summary else "",
                    "relevance": kw.weight,
                })
    return results[:limit]


def _tfidf_match(db: DBSession, project_id: int, query: str, limit: int = 5) -> list[dict]:
    """L2: TF-IDF-like relevance from summary topic text (<100ms)."""
    summaries = (
        db.query(Summary)
        .join(Summary.session)
        .filter(Summary.session.has(project_id=project_id))
        .all()
    )
    query_words = set(query.lower().split())
    if not query_words:
        return []

    scored = []
    for s in summaries:
        text = ((s.topic or "") + " " + (s.conclusions or "")).lower()
        text_words = set(text.split())
        overlap = query_words & text_words
        if overlap:
            scored.append({
                "source": "L2_tfidf",
                "session_id": s.session_id,
                "summary": s.topic or "",
                "relevance": len(overlap) / max(len(query_words), 1),
            })
    scored.sort(key=lambda x: x["relevance"], reverse=True)
    return scored[:limit]


def _vector_match(query: str, project_id: int, limit: int = 5) -> list[dict]:
    """L3: vector semantic search via ChromaDB (<500ms)."""
    try:
        results = search_similar("classification_nodes", query, top_k=limit)
        enriched = []
        for r in results:
            enriched.append({
                "source": "L3_vector",
                "node_id": r["id"],
                "distance": r["distance"],
                "document": r.get("document", ""),
            })
        return enriched
    except Exception:
        return []


def prefetch_context(db: DBSession, project_id: int, query: str, max_tokens: int = 2000) -> list[dict]:
    """L1→L2→L3 progressive memory search with token budget control."""
    results = []

    # L1: keyword match
    l1 = _keyword_match(db, project_id, query)
    results.extend(l1)

    # L2: TF-IDF if L1 insufficent
    if len(results) < 3:
        l2 = _tfidf_match(db, project_id, query)
        for item in l2:
            if not any(r.get("session_id") == item["session_id"] for r in results):
                results.append(item)

    # L3: Vector search if still insufficient
    if len(results) < 3:
        l3 = _vector_match(query, project_id)
        results.extend(l3)

    # Token budget: trim
    total_chars = 0
    trimmed = []
    for item in results:
        chars = len(item.get("summary", "")) + len(item.get("document", ""))
        if total_chars > max_tokens * 2:
            break
        total_chars += chars
        trimmed.append(item)

    # Also include failed approaches from classification nodes
    failed_nodes = (
        db.query(ClassificationNode)
        .filter(
            ClassificationNode.project_id == project_id,
            ClassificationNode.failed_approaches != "[]",
            ClassificationNode.failed_approaches != "",
        )
        .limit(5)
        .all()
    )
    failed_list = []
    for node in failed_nodes:
        try:
            arr = json.loads(node.failed_approaches)
            if arr:
                failed_list.append({
                    "source": "failed_approaches",
                    "category": node.category_name,
                    "approaches": arr,
                })
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "context_items": trimmed,
        "failed_approaches": failed_list,
    }
