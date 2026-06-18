from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.database import Base


class ActionMemory(Base):
    __tablename__ = "action_memories"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    action = Column(Text, nullable=False)
    permissions = Column(Text, default="")
    timing = Column(Text, default="")
    expiry = Column(String(64), default="")
    source_authority = Column(String(32), default="medium")
