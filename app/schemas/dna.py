from typing import Optional, List
from pydantic import BaseModel


class DNAOut(BaseModel):
    id: int
    project_id: int
    goals: str
    successful_approaches: str
    failed_approaches: str
    tools: str
    models: str
    next_plans: str
    updated_at: str

    model_config = {"from_attributes": True}


class DNAUpdate(BaseModel):
    goals: Optional[List[str]] = None
    successful_approaches: Optional[List[str]] = None
    failed_approaches: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    models: Optional[List[str]] = None
    next_plans: Optional[List[str]] = None
