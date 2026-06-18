from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    topic = Column(Text, default="")
    conclusions = Column(Text, default="")
    decisions = Column(Text, default="")
    next_steps = Column(Text, default="")
    created_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    session = relationship("Session", back_populates="summary")
