from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base


class ApprovalLog(Base):
    """Auto-approved writes — transparent audit trail."""
    __tablename__ = "approval_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    operation = Column(String, default="")
    subsystem = Column(String, default="")
    scope = Column(String, default="")
    origin = Column(String, default="")
    risk_score = Column(Float, default=0.0)
    threshold = Column(Float, default=0.45)
    decision = Column(String, default="auto_approved")
    detail = Column(Text, default="")
    created_at = Column(String, default="")
