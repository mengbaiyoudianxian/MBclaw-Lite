from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    thinking_content = Column(Text, default="")
    changed_files = Column(Text, default="[]")
    created_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    session = relationship("Session", back_populates="messages")
