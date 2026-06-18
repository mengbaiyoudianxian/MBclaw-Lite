from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.models.session import Session
from app.models.summary import Summary
from app.schemas.session import SessionCreate, SessionOut
from app.services.summary_service import generate_summary
from app.services.keyword_service import extract_keywords
from app.services.dna_service import update_dna_from_session
from app.services.memory_service import memory_flush
from app.services.transcript_service import write_final_transcript
from app.services.action_memory_service import extract_action_memories
from app.services.classification_service import classify_session

router = APIRouter(prefix="/api/projects/{project_id}/sessions", tags=["sessions"])


def _get_project(project_id: int, db: DBSession) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=SessionOut, status_code=201)
def create_session(project_id: int, data: SessionCreate, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    max_num = db.query(Session).filter(Session.project_id == project_id).count()
    session = Session(
        project_id=project_id,
        session_number=max_num + 1,
        title=data.title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[SessionOut])
def list_sessions(project_id: int, db: DBSession = Depends(get_db)):
    _get_project(project_id, db)
    return db.query(Session).filter(Session.project_id == project_id).all()


@router.patch("/{session_id}/complete", response_model=SessionOut)
def complete_session(project_id: int, session_id: int, db: DBSession = Depends(get_db)):
    _get_project(project_id, db)
    session = db.query(Session).filter(Session.id == session_id, Session.project_id == project_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "completed"
    session.ended_at = datetime.now().isoformat()

    # Phase 1: generate summary + keywords + update DNA
    generate_summary(db, session)
    extract_keywords(db, session)
    update_dna_from_session(db, session.project)

    # Phase 2 (OpenClaw-inspired): memory flush + JSONL transcript + action memories
    memory_flush(db, session)
    write_final_transcript(db, session)
    for am in extract_action_memories(db, session):
        db.add(am)
    # Project 2: tree classification
    classify_session(db, session)

    db.commit()
    db.refresh(session)
    return session
