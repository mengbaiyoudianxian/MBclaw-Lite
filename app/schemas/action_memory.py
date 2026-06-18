from pydantic import BaseModel, ConfigDict


class ActionMemoryBase(BaseModel):
    action: str
    permissions: str = ""
    timing: str = ""
    expiry: str = ""
    source_authority: str = "medium"


class ActionMemoryCreate(ActionMemoryBase):
    pass


class ActionMemoryOut(ActionMemoryBase):
    id: int
    session_id: int | None = None
    project_id: int

    model_config = ConfigDict(from_attributes=True)
