from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    session_number = Column(Integer, nullable=False)
    title = Column(String, default="")
    status = Column(String, nullable=False, default="active")
    context = Column(String, default="")
    started_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())
    ended_at = Column(String, nullable=True)

    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.id")
    summary = relationship("Summary", back_populates="session", uselist=False, cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="session", cascade="all, delete-orphan")
    classification_nodes = relationship("ClassificationNode", back_populates="session", cascade="all, delete-orphan")
