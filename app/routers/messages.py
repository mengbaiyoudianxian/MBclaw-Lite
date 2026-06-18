from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.session import Session
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageOut
from app.services.transcript_service import append_to_transcript

router = APIRouter(prefix="/api/sessions/{session_id}/messages", tags=["messages"])


def _get_session(session_id: int, db: DBSession) -> Session:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    return session


@router.post("", response_model=MessageOut, status_code=201)
def add_message(session_id: int, data: MessageCreate, db: DBSession = Depends(get_db)):
    session = _get_session(session_id, db)
    if data.role not in ("user", "assistant", "system"):
        raise HTTPException(status_code=400, detail="Role must be user, assistant, or system")
    msg = Message(
        session_id=session.id,
        role=data.role,
        content=data.content,
        thinking_content=data.thinking_content,
        changed_files=data.changed_files,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Phase 2: append to JSONL transcript (enhanced with thinking + changed_files)
    append_to_transcript(session, {
        "role": msg.role,
        "content": msg.content,
        "thinking_content": msg.thinking_content,
        "changed_files": msg.changed_files,
        "created_at": msg.created_at,
    })

    return msg


@router.get("", response_model=list[MessageOut])
def list_messages(session_id: int, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return db.query(Message).filter(Message.session_id == session_id).order_by(Message.id).all()
