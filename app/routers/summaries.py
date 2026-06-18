from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.session import Session
from app.models.summary import Summary
from app.schemas.summary import SummaryOut
from app.services.summary_service import generate_summary

router = APIRouter(prefix="/api/sessions/{session_id}/summary", tags=["summaries"])


@router.get("", response_model=SummaryOut)
def get_summary(session_id: int, db: DBSession = Depends(get_db)):
    summary = db.query(Summary).filter(Summary.session_id == session_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found. Complete the session first.")
    return summary


@router.post("", response_model=SummaryOut)
def regenerate_summary(session_id: int, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = generate_summary(db, session)
    db.commit()
    db.refresh(summary)
    return summary
