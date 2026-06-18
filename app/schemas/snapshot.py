from pydantic import BaseModel, ConfigDict


class SnapshotOut(BaseModel):
    id: int
    project_id: int
    path: str
    reason: str
    trigger_rule: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class SnapshotRestoreResult(BaseModel):
    success: bool
    snapshot_id: int
    message: str
