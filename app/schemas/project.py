from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
