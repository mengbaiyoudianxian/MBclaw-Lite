from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.schemas.dna import DNAOut, DNAUpdate
from app.services.dna_service import get_or_create_dna, update_dna

router = APIRouter(prefix="/api/projects/{project_id}", tags=["dna"])


@router.get("/dna", response_model=DNAOut)
def get_dna(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_or_create_dna(db, project)


@router.patch("/dna", response_model=DNAOut)
def patch_dna(project_id: int, data: DNAUpdate, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    dna = update_dna(db, project, data)
    db.commit()
    db.refresh(dna)
    return dna
