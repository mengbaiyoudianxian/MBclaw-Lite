"""T5.1 — REST API router (5 endpoints).

Never imports Summary/Keyword/Experience directly (铁律 #5 + CI guard).
"""

import fcntl
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import LLMClient, get_llm
from app.memory import MemoryRepo
from app.models import Message, Session as SessionModel  # orchestrator-only
from app.pipeline import close_session

router = APIRouter()

# ── JSONL transcript helper ─────────────────────────────────

TRANSCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")


def _append_transcript(sid: int, msg: dict) -> None:
    """Thread-safe append of a single message to a session transcript JSONL."""
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    path = os.path.join(TRANSCRIPT_DIR, f"session-{sid}.jsonl")
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    with open(path, "a") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            fp.write(line)
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

# ── request / response schemas ──────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str = ""


class SessionResponse(BaseModel):
    session_id: int
    title: str
    status: str
    injected_system_message: dict | None = None


class AddMessageRequest(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime


class CloseResponse(BaseModel):
    session_id: int
    status: str
    summary: str
    keywords: list[dict]
    experiences: list[dict]
    stats: dict


class SearchHit(BaseModel):
    session_id: int
    summary: str
    keywords: list[str]
    score: float


# ── endpoints ───────────────────────────────────────────────


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    req: CreateSessionRequest,
    db: Session = Depends(get_db),
):
    """Create a new session with optional memory injection."""
    session = SessionModel(title=req.title, status="active")
    db.add(session)
    db.commit()
    db.refresh(session)

    injected = None
    repo = MemoryRepo(db)
    rendered = repo.render_injection_for_new_session(exclude_sid=session.id)
    if rendered:
        injected = {"role": "system", "content": rendered}
        db.add(Message(session_id=session.id, role="system", content=rendered))
        db.commit()

    return SessionResponse(
        session_id=session.id,
        title=session.title,
        status=session.status,
        injected_system_message=injected,
    )


@router.post("/sessions/{sid}/messages", response_model=MessageResponse)
def add_message(
    sid: int,
    req: AddMessageRequest,
    db: Session = Depends(get_db),
):
    """Append a message to a session and the JSONL transcript."""
    session = db.query(SessionModel).filter(SessionModel.id == sid).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "closed":
        raise HTTPException(400, "Session is closed")

    msg = Message(session_id=sid, role=req.role, content=req.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    _append_transcript(sid, {
        "id": msg.id, "session_id": sid, "role": msg.role,
        "content": msg.content, "created_at": msg.created_at.isoformat(),
    })

    return MessageResponse(
        id=msg.id, session_id=msg.session_id,
        role=msg.role, content=msg.content, created_at=msg.created_at,
    )


@router.post("/sessions/{sid}/close", response_model=CloseResponse)
def close(
    sid: int,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """Close a session: summarise, persist memory, mark closed."""
    try:
        result = close_session(db, sid, llm)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return CloseResponse(**result)


@router.get("/sessions/{sid}/messages", response_model=list[MessageResponse])
def list_messages(
    sid: int,
    db: Session = Depends(get_db),
):
    """Return all messages for a session in chronological order."""
    msgs = db.query(Message).filter(
        Message.session_id == sid
    ).order_by(Message.created_at).all()
    return [
        MessageResponse(
            id=m.id, session_id=m.session_id,
            role=m.role, content=m.content, created_at=m.created_at,
        )
        for m in msgs
    ]


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Full-text + keyword search across past session summaries."""
    repo = MemoryRepo(db)
    hits = repo.query(q, top_n=limit)
    return [SearchHit(
        session_id=h.session_id, summary=h.summary,
        keywords=h.keywords, score=h.score,
    ) for h in hits]
