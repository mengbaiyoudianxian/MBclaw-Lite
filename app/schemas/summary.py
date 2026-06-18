from pydantic import BaseModel


class SummaryOut(BaseModel):
    id: int
    session_id: int
    topic: str
    conclusions: str
    decisions: str
    next_steps: str
    created_at: str

    model_config = {"from_attributes": True}
