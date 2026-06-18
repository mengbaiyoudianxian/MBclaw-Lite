from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.models.action_memory import ActionMemory
from app.schemas.action_memory import ActionMemoryCreate, ActionMemoryOut

router = APIRouter(prefix="/api/projects/{project_id}/actions", tags=["action_memories"])


@router.get("", response_model=list[ActionMemoryOut])
def list_actions(project_id: int, authority: str = None, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    q = db.query(ActionMemory).filter(ActionMemory.project_id == project_id)
    if authority:
        q = q.filter(ActionMemory.source_authority == authority)
    return q.order_by(ActionMemory.id.desc()).limit(50).all()


@router.post("", response_model=ActionMemoryOut)
def create_action(project_id: int, data: ActionMemoryCreate, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    am = ActionMemory(
        project_id=project_id,
        action=data.action, permissions=data.permissions,
        timing=data.timing, expiry=data.expiry,
        source_authority=data.source_authority,
    )
    db.add(am)
    db.commit()
    db.refresh(am)
    return am
