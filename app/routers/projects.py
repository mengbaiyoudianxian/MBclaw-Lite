from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: DBSession = Depends(get_db)):
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=400, detail="Create a user first")
    project = Project(user_id=user.id, name=data.name, description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: DBSession = Depends(get_db)):
    return db.query(Project).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
