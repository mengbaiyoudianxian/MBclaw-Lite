from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    created_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())
    updated_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    sessions = relationship("Session", back_populates="project", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="project", cascade="all, delete-orphan")
    dna = relationship("ProjectDNA", back_populates="project", uselist=False, cascade="all, delete-orphan")
