from pydantic import BaseModel


class KeywordOut(BaseModel):
    id: int
    session_id: int
    project_id: int
    keyword: str
    weight: float

    model_config = {"from_attributes": True}
