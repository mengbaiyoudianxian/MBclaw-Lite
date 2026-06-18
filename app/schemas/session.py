from typing import Optional
from pydantic import BaseModel


class SessionCreate(BaseModel):
    title: str = ""


class SessionOut(BaseModel):
    id: int
    project_id: int
    session_number: int
    title: str
    status: str
    started_at: str
    ended_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionComplete(BaseModel):
    pass
