"""T4.1 — Session-close pipeline.

Orchestrates: load messages → LLM summarise → jieba TF-IDF →
MemoryRepo write → close session.  Single entry-point: close_session().
"""

from datetime import datetime, timezone

import jieba.analyse

from app.llm import LLMClient, LLMOutput
from app.memory import MemoryRepo
from app.models import Message, Session  # orchestrator-only imports


def close_session(db, sid: int, llm: LLMClient) -> dict:
    """Close a session: summarise, persist memory, mark closed.

    Idempotent: if already closed returns stored result without re-calling LLM.
    """
    session = db.query(Session).filter(Session.id == sid).first()
    if not session:
        raise ValueError(f"Session {sid} not found")

    if session.status == "closed":
        repo = MemoryRepo(db)
        hits = repo.query(f"session {sid}", top_n=1)
        return {
            "session_id": sid, "status": "closed",
            "summary": hits[0].summary if hits else "",
            "keywords": hits[0].keywords if hits else [],
            "experiences": [],
            "stats": {"cached": True},
        }

    # 1. Load messages
    messages = db.query(Message).filter(Message.session_id == sid).order_by(Message.created_at).all()
    if not messages:
        raise ValueError(f"No messages in session {sid}")

    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

    # 2. LLM summarise
    llm_out: LLMOutput = llm.summarize_session(msg_dicts)

    # 3. jieba TF-IDF keywords (top 10, merge with LLM)
    all_text = " ".join(m.content for m in messages)
    jieba_kws = jieba.analyse.extract_tags(all_text, topK=10, withWeight=True)
    kw_map: dict[str, float] = {}
    for kw in llm_out.keywords:
        kw_map[kw] = kw_map.get(kw, 0) + 1.0
    for kw, weight in jieba_kws:
        kw_map[kw] = kw_map.get(kw, 0) + 0.5 * weight
    merged_kws = sorted(kw_map.items(), key=lambda x: x[1], reverse=True)[:10]

    # 4. Persist via MemoryRepo
    exp_dicts = [e.model_dump() for e in llm_out.experiences]
    MemoryRepo(db).write_session_memory(
        sid, llm_out.summary, [k for k, _ in merged_kws], exp_dicts,
    )

    # 5. Mark closed
    session.status = "closed"
    session.ended_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "session_id": sid,
        "status": "closed",
        "summary": llm_out.summary,
        "keywords": [{"keyword": k, "weight": w} for k, w in merged_kws],
        "experiences": exp_dicts,
        "stats": {"message_count": len(messages), "cached": False},
    }
