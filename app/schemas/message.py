from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    role: str
    content: str
    thinking_content: str = ""
    changed_files: str = "[]"


class MessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    thinking_content: str = ""
    changed_files: str = "[]"
    created_at: str

    model_config = ConfigDict(from_attributes=True)
