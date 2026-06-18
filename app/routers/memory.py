from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from app.database import get_db
from app.models.project import Project
from app.services.memory_service import (
    read_memory_md, write_memory_md, read_daily_notes,
    append_daily_note, read_dreams, dream,
)

router = APIRouter(prefix="/api/projects/{project_id}/memory", tags=["memory"])


class MemoryWrite(BaseModel):
    content: str


class DailyNote(BaseModel):
    content: str


class DreamOut(BaseModel):
    candidates: int
    promoted: int


def _get_project(project_id: int, db: DBSession) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ---- Tier 1: MEMORY.md ----

@router.get("/durable")
def get_durable_memory(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_memory_md(project.name)
    return {"project": project.name, "content": content}


@router.put("/durable")
def set_durable_memory(project_id: int, data: MemoryWrite, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    write_memory_md(project.name, data.content)
    return {"project": project.name, "status": "saved"}


# ---- Tier 2: Daily Notes ----

@router.get("/daily")
def get_daily_notes(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_daily_notes(project.name)
    return {"project": project.name, "content": content}


@router.post("/daily")
def add_daily_note(project_id: int, data: DailyNote, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    append_daily_note(project.name, data.content)
    return {"project": project.name, "status": "appended"}


# ---- Tier 3: Dreams ----

@router.get("/dreams")
def get_dreams(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    content = read_dreams(project.name)
    return {"project": project.name, "content": content}


@router.post("/dream", response_model=DreamOut)
def run_dream(project_id: int, db: DBSession = Depends(get_db)):
    project = _get_project(project_id, db)
    result = dream(db, project)
    db.commit()
    return result
