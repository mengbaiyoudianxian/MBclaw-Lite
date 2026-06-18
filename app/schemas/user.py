from datetime import datetime
from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str


class UserOut(BaseModel):
    id: int
    name: str
    created_at: str

    model_config = {"from_attributes": True}
