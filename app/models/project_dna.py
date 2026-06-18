from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class ProjectDNA(Base):
    __tablename__ = "project_dna"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    goals = Column(Text, default="[]")
    successful_approaches = Column(Text, default="[]")
    failed_approaches = Column(Text, default="[]")
    tools = Column(Text, default="[]")
    models = Column(Text, default="[]")
    next_plans = Column(Text, default="[]")
    updated_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    project = relationship("Project", back_populates="dna")
