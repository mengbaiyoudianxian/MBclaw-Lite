from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.models.keyword import Keyword
from app.schemas.keyword import KeywordOut

router = APIRouter(prefix="/api/projects/{project_id}", tags=["keywords"])


@router.get("/keywords", response_model=list[KeywordOut])
def get_project_keywords(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Keyword).filter(Keyword.project_id == project_id).all()
