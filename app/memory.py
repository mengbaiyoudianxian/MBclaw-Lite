"""T3.1–T3.4 — MemoryRepo: dual-recall memory abstraction layer.

All business code MUST go through MemoryRepo — never import models directly
in api.py or pipeline.py (铁律 #5).
"""

import json
import math
import os
from datetime import datetime, timezone

import jieba
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.models import Experience, Keyword, Session, Summary


class MemoryHit(BaseModel):
    session_id: int
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    score: float = 0.0
    source: str = ""  # "fts" | "keywords" | "both"


class MemoryRepo:
    def __init__(self, db_session):
        self.db = db_session

    # ── T3.1 write ─────────────────────────────────────────

    def write_session_memory(self, sid: int, summary: str, keywords: list[str],
                             experiences: list[dict]) -> None:
        """Atomic write: summary + keywords + experiences (≤5)."""
        # summary: delete old then insert (avoid merge-without-pk UNIQUE error)
        self.db.query(Summary).filter(Summary.session_id == sid).delete()
        self.db.add(Summary(session_id=sid, summary=summary))
        # keywords: replace
        self.db.query(Keyword).filter(Keyword.session_id == sid).delete()
        for kw in keywords:
            self.db.add(Keyword(session_id=sid, keyword=kw, weight=1.0))
        # experiences: append (≤5)
        for exp in experiences[:5]:
            self.db.add(Experience(
                session_id=sid, kind=exp.get("kind", "lesson"),
                title=exp.get("title", ""), content=exp.get("content", ""),
                keywords_json=json.dumps(exp.get("keywords", []), ensure_ascii=False),
            ))
        self.db.commit()
        self._maybe_evict_experiences()

    # ── T3.2 dual-recall query ─────────────────────────────

    def query(self, q: str, top_n: int = 3) -> list[MemoryHit]:
        """Dual-recall: FTS5 (messages_fts) + jieba keyword match."""
        hits: dict[int, MemoryHit] = {}
        tokens = list(jieba.cut_for_search(q))

        # A. FTS recall
        try:
            rows = self.db.execute(text(
                "SELECT m.session_id, s.summary, rank AS score "
                "FROM messages_fts JOIN messages m ON m.id=messages_fts.rowid "
                "JOIN summaries s ON s.session_id=m.session_id "
                "WHERE messages_fts MATCH :q "
                "GROUP BY m.session_id ORDER BY score"
            ), {"q": _fts_escape(q)}).fetchall()
        except Exception:
            rows = []
        fts_max = max((r[2] for r in rows), default=1.0)
        for sid, summary, score in rows:
            hits[sid] = MemoryHit(
                session_id=sid, summary=summary or "",
                score=0.6 * abs(score / fts_max) if fts_max else 0,
                source="fts")

        # B. keyword recall
        if tokens:
            kw_rows = self.db.query(
                Keyword.session_id, Summary.summary, Keyword.keyword
            ).join(Summary, Summary.session_id == Keyword.session_id).filter(
                Keyword.keyword.in_(tokens)).all()
            kw_count: dict[int, int] = {}
            for sid, summary, kw in kw_rows:
                kw_count[sid] = kw_count.get(sid, 0) + 1
                if sid not in hits:
                    hits[sid] = MemoryHit(session_id=sid, summary=summary or "", source="keywords")
                hits[sid].keywords.append(kw)
            kw_max = max(kw_count.values(), default=1)
            for sid, cnt in kw_count.items():
                hits[sid].score += 0.4 * (cnt / kw_max)
                hits[sid].source = "both" if hits[sid].source == "fts" else "keywords"

        return sorted(hits.values(), key=lambda h: h.score, reverse=True)[:top_n]

    # ── T3.3 experiences + render ──────────────────────────

    def query_experiences(self, q: str, top_n: int = 2) -> list[dict]:
        """FTS5 on experiences_fts + kind-priority + recency bonus."""
        pri = {"failure": 1.0, "lesson": 0.8, "success": 0.5}
        try:
            rows = self.db.execute(text(
                "SELECT e.id, e.session_id, e.kind, e.title, e.content, "
                "e.recall_count, rank AS score "
                "FROM experiences_fts JOIN experiences e ON e.id=experiences_fts.rowid "
                "WHERE experiences_fts MATCH :q ORDER BY score"
            ), {"q": _fts_escape(q)}).fetchall()
        except Exception:
            return []
        scored = []
        for eid, sid, kind, title, content, rc, fts in rows:
            bonus = pri.get(kind, 0.3) + math.log(rc + 1)
            scored.append((0.7 * fts + 0.3 * bonus,
                           {"id": eid, "session_id": sid, "kind": kind,
                            "title": title, "content": content, "recall_count": rc}))
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, exp in scored[:top_n]:
            self.db.query(Experience).filter(Experience.id == exp["id"]).update({
                "last_recalled_at": datetime.now(timezone.utc),
                "recall_count": Experience.recall_count + 1,
            }, synchronize_session=False)
        self.db.commit()
        return [e for _, e in scored[:top_n]]

    def render_injection_for_new_session(self, exclude_sid: int | None = None) -> str | None:
        """Self-prime: last closed session → query → ≤800-char template."""
        last = self.db.query(Session).filter(
            Session.status == "closed", Session.id != exclude_sid
        ).order_by(Session.ended_at.desc()).first()
        if not last:
            return None
        s = self.db.query(Summary).filter(Summary.session_id == last.id).first()
        kws = self.db.query(Keyword).filter(Keyword.session_id == last.id).all()
        if not s:
            return None
        q = s.summary[:200] + " " + " ".join(k.keyword for k in kws[:5])
        sum_hits = self.query(q, 3)
        exp_hits = self.query_experiences(q, 2)

        blocks: list[str] = []
        if sum_hits:
            blocks.append("【上次的关键事实】\n" + "\n".join(
                f"- [#{h.session_id}] {h.summary[:120]}  关键词: {', '.join(h.keywords[:3])}"
                for h in sum_hits))

        fl = [e for e in exp_hits if e["kind"] in ("failure", "lesson")]
        if fl:
            icons = {"failure": "⚠️", "lesson": "💡"}
            blocks.append("【避免重复的失败】\n" + "\n".join(
                f"- {icons.get(e['kind'], '-')} [#{e['session_id']}] {e['title']}" for e in fl))

        succ = [e for e in exp_hits if e["kind"] == "success"]
        if succ:
            blocks.append("【已验证的成功】\n" + "\n".join(
                f"- ✅ [#{e['session_id']}] {e['title']}" for e in succ))

        return ("\n\n".join(blocks))[:800] if blocks else None

    # ── T3.4 eviction ──────────────────────────────────────

    def _maybe_evict_experiences(self) -> int:
        """Archive oldest experiences when count > 1000."""
        total = self.db.query(Experience).count()
        if total <= 1000:
            return 0
        old = self.db.query(Experience).order_by(
            Experience.created_at.asc()).limit(total - 1000).all()
        if not old:
            return 0
        arc = os.path.join(os.path.dirname(__file__), "..", "data", "archive")
        os.makedirs(arc, exist_ok=True)
        p = os.path.join(arc, f"experiences-{datetime.now(timezone.utc).strftime('%Y-%m')}.jsonl")
        with open(p, "a") as fh:
            for e in old:
                fh.write(json.dumps({
                    "id": e.id, "session_id": e.session_id, "kind": e.kind,
                    "title": e.title, "content": e.content,
                    "keywords_json": e.keywords_json,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "recall_count": e.recall_count,
                }, ensure_ascii=False) + "\n")
        for e in old:
            self.db.delete(e)
        self.db.commit()
        return len(old)


def _fts_escape(q: str) -> str:
    """Escape FTS5 special characters so user input doesn't break MATCH."""
    return q.replace('"', '""').replace("'", "''")


# ── Memory System v1: write_v2 + search_v2 ──
import struct as _sv2

def write_v2_memory(db, workspace_id, session_id, encoder_result):
    import json
    written = []
    for mem_type, items in [
        ("episode", encoder_result.episodes),
        ("semantic", encoder_result.semantics),
        ("procedure", encoder_result.procedures),
        ("failure", encoder_result.failures),
    ]:
        for item in items:
            content = json.dumps(item.__dict__ if hasattr(item,"__dict__") else item, ensure_ascii=False)
            emb_blob = None
            try:
                from app.llm import LLMClient
                vec = LLMClient().embed(content)
                if vec and len(vec) >= 100:
                    emb_blob = _sv2.pack("<" + str(len(vec)) + "f", *vec)
            except: pass
            imp = {"failure":0.85,"procedure":0.70,"semantic":0.50,"episode":0.30}.get(mem_type,0.50)
            tags = json.dumps(getattr(item,"tags",[]) or [], ensure_ascii=False)
            from app.models import Memory
            m = Memory(workspace_id=workspace_id, session_id=session_id, type=mem_type,
                       content_json=content, embedding=emb_blob, importance_score=imp, tags=tags)
            db.add(m); written.append(m)
    db.commit()
    return written

def search_v2_memory(db, workspace_id, query, top_k=5):
    from app.retrieval import hybrid_search
    from app.llm import LLMClient
    vec = None
    try: vec = LLMClient().embed(query)
    except: pass
    results = hybrid_search(db, workspace_id, query, vec, top_k)
    for r in results:
        m = r.get("_memory_obj")
        if m:
            m.usage_count = (m.usage_count or 0) + 1
            import time as _t2; m.last_used_at = _t2.strftime("%Y-%m-%dT%H:%M:%SZ", _t2.gmtime())
    db.commit()
    return results


# ── Phase1: raw memory write + phase-1 search ──────────────

def write_raw_memory(db, workspace_id: int, entries: list[dict]) -> list[str]:
    """Batch-write raw memory entries via phase1_db.

    Each entry dict: role, content, content_type (default "text"), parent_id (optional).
    Ensures raw_memories / raw_memories_fts / memory_nodes tables exist before writing.
    """
    from app.phase1_db import run_migration, write_raw

    run_migration()
    ids: list[str] = []
    for entry in entries:
        mid = write_raw(
            db,
            workspace_id=workspace_id,
            role=entry.get("role", "user"),
            content=entry.get("content", ""),
            content_type=entry.get("content_type", "text"),
            parent_id=entry.get("parent_id"),
        )
        ids.append(mid)
    return ids


def search_phase1(workspace_id, query: str, limit: int = 20) -> list[dict]:
    """Phase-1 dual search: FTS5 on raw_memories + LIKE on memory_nodes.

    Returns unified list of dicts with keys:
        id, type, text, score, importance, created_at
    Compatible with app.context.builder.ContextBuilder.build.
    """
    from app.phase1_db import run_migration
    from app.db import SessionLocal

    run_migration()

    try:
        ws_id = int(workspace_id)
    except (TypeError, ValueError):
        ws_id = workspace_id

    db = SessionLocal()
    try:
        results: list[dict] = []

        # ── A. FTS5 search on raw_memories ──
        try:
            fts_rows = db.execute(
                text(
                    "SELECT r.id, r.workspace_id, r.role, r.content, r.content_type, "
                    "r.created_at, snippet(raw_memories_fts, 0, '', '', '...', 40) AS snippet, "
                    "rank AS score "
                    "FROM raw_memories_fts f JOIN raw_memories r ON f.rowid = r.rowid "
                    "WHERE raw_memories_fts MATCH :q AND r.workspace_id = :ws "
                    "AND r.is_archived = 0 "
                    "ORDER BY rank LIMIT :lim"
                ),
                {"q": _fts_escape(query), "ws": ws_id, "lim": limit},
            ).fetchall()

            for row in fts_rows:
                results.append({
                    "id": row.id,
                    "type": row.role,
                    "text": row.snippet or row.content[:200],
                    "score": round(1.0 / (1.0 + abs(row.score)) if row.score else 0.5, 4),
                    "importance": 0.5,
                    "created_at": row.created_at,
                })
        except Exception:
            pass

        # ── B. LIKE search on memory_nodes ──
        try:
            tokens = [t for t in query.split() if len(t) >= 2]
            if tokens:
                clauses = " OR ".join(
                    f"(summary LIKE :t{i} OR content_json LIKE :t{i})"
                    for i in range(len(tokens))
                )
                params: dict = {"ws": ws_id, "lim": limit}
                for i, t in enumerate(tokens):
                    params[f"t{i}"] = f"%{t}%"

                node_rows = db.execute(
                    text(
                        f"SELECT id, workspace_id, layer, content_json, summary, "
                        f"importance, quality_score, created_at "
                        f"FROM memory_nodes "
                        f"WHERE workspace_id = :ws AND ({clauses}) "
                        f"ORDER BY importance DESC, quality_score DESC LIMIT :lim"
                    ),
                    params,
                ).fetchall()

                for row in node_rows:
                    results.append({
                        "id": row.id,
                        "type": row.layer,
                        "text": row.summary or row.content_json[:200],
                        "score": round(row.quality_score or 0.5, 4),
                        "importance": round(row.importance or 0.5, 4),
                        "created_at": row.created_at,
                    })
        except Exception:
            pass

        # ── deduplicate by id ──
        seen: set[str] = set()
        unique: list[dict] = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        # ── sort by combined score ──
        unique.sort(key=lambda x: x["score"] * 0.6 + x["importance"] * 0.4, reverse=True)
        return unique[:limit]

    finally:
        db.close()
# Phase1: Raw Memory + FTS5 Search
import json as _ph1_json

def write_raw_memory(db, workspace_id, role, content, content_type='text', parent_id=None):
    from app.phase1_models import RawMemory
    m = RawMemory(workspace_id=workspace_id, role=role, content=content,
                  content_type=content_type, parent_id=parent_id)
    db.add(m); db.commit()
    return m.id

def search_phase1(db, workspace_id, query, top_k=5):
    from app.phase1_db import search_fts as _fts
    results = _fts(query, workspace_id, top_k)
    enriched = []
    for row in results:
        item = dict(row) if hasattr(row, 'keys') else row
        item['score'] = 1.0
        enriched.append(item)
    from app.models import Memory as _M
    failures = db.query(_M).filter(
        _M.workspace_id == workspace_id, _M.type == 'failure'
    ).order_by(_M.importance_score.desc()).limit(3).all()
    for f in failures:
        enriched.append({
            'id': f.id, 'type': 'failure',
            'content': _ph1_json.loads(f.content_json) if f.content_json else {},
            'summary': f.summary or '',
            'importance': f.importance_score,
            'score': f.importance_score * 1.5,
            'source': 'memory_node',
        })
    enriched.sort(key=lambda x: x.get('score', 0), reverse=True)
    return enriched[:top_k]
