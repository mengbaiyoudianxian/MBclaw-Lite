from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotOut, SnapshotRestoreResult
from app.services.snapshot_service import create_snapshot, restore_snapshot

router = APIRouter(prefix="/api/projects/{project_id}/snapshots", tags=["snapshots"])


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.query(Snapshot).filter(Snapshot.project_id == project_id).order_by(
        Snapshot.created_at.desc()
    ).all()


@router.post("", response_model=SnapshotOut, status_code=201)
def create_manual_snapshot(project_id: int, reason: str = "手动创建",
                           db: DBSession = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return create_snapshot(db, project_id, reason=reason, trigger_rule="manual")


@router.post("/restore/{snapshot_id}", response_model=SnapshotRestoreResult)
def restore(project_id: int, snapshot_id: int, db: DBSession = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(
        Snapshot.id == snapshot_id, Snapshot.project_id == project_id
    ).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    return restore_snapshot(db, snapshot_id)
