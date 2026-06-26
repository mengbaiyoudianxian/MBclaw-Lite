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

def _write_memory_v2(db, sid, llm, workspace_id=None):
    try:
        from app.models import Message, Session
        from app.encoder import MemoryEncoder
        from app.memory import write_v2_memory
        from app.deduplicator import Deduplicator
        from app.phase1_models import MemoryNode
        from app.llm import LLMClient as _LC
        import json as _j, struct as _st

        if workspace_id is None:
            sess = db.get(Session, sid)
            workspace_id = sess.workspace_id if sess and sess.workspace_id else 1
        msgs = db.query(Message).filter(Message.session_id==sid).order_by(Message.created_at).all()
        msg_dicts = [{"role":m.role,"content":m.content} for m in msgs]
        enc = MemoryEncoder(llm)
        result = enc.encode(msg_dicts, workspace_id)

        dedup = Deduplicator(threshold=0.85)
        existing = db.query(MemoryNode).filter(MemoryNode.workspace_id==workspace_id).all()
        llm_embed = _LC()
        merged_count = 0

        for mem_type, items in [
            ("episode", result.episodes),
            ("semantic", result.semantics),
            ("procedure", result.procedures),
            ("failure", result.failures),
        ]:
            kept = []
            for item in items:
                try:
                    content_str = _j.dumps(item.__dict__ if hasattr(item,"__dict__") else item, ensure_ascii=False)
                    emb_vec = llm_embed.embed(content_str)
                    if emb_vec and len(emb_vec) >= 100:
                        emb_blob = _st.pack("<" + str(len(emb_vec)) + "f", *emb_vec)
                    else:
                        emb_blob = None
                    dup, sim = dedup.find_duplicate(emb_vec, existing) if emb_blob else (None, 0)
                    if dup:
                        merged = dedup.merge(dup, item, emb_vec, sim)
                        dup.content_json = merged["content_json"]
                        dup.importance = merged["importance"]
                        dup.embedding = merged["embedding"]
                        dup.tags = merged["tags"]
                        merged_count += 1
                    else:
                        kept.append(item)
                except Exception:
                    kept.append(item)
            if mem_type == "episode": result.episodes = kept
            elif mem_type == "semantic": result.semantics = kept
            elif mem_type == "procedure": result.procedures = kept
            else: result.failures = kept

        written = write_v2_memory(db, workspace_id, sid, result) if result.total_count > 0 else []
        if len(written) > 2:
            from app.l3_refiner import submit_async
            submit_async(written, workspace_id)
        return {"ok":True,"count":len(written),"merged":merged_count}
    except Exception as e:
        import logging
        logging.getLogger("mbclaw").warning("v2 failed, bypass: %s", str(e))
        return {"ok":False,"error":str(e)}