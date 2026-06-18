from pydantic import BaseModel


class ApprovalThresholdUpdate(BaseModel):
    level: str | None = None  # minimal, low, medium, high, maximum, full_auto
    custom: float | None = None


class WriteApprovalRequest(BaseModel):
    user_id: int
    subsystem: str
    scope: str
    origin: str
    content_chars: int = 0
    modifies_existing: str = "pure_add"
    detail: str = ""
    payload: dict | None = None
