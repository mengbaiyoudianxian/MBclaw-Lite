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

