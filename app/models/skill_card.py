from sqlalchemy import Column, Integer, String, Text, Boolean
from app.database import Base


class SkillCard(Base):
    """Procedural memory: reusable skill extracted from agent experience.
    Separate from declarative memory (MEMORY.md, ProjectDNA, Summary).
    """
    __tablename__ = "skill_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    trigger_condition = Column(Text, default="")
    steps = Column(Text, default="[]")
    known_pitfalls = Column(Text, default="[]")
    category = Column(String, default="")
    created_by = Column(String, default="user")
    pinned = Column(Boolean, default=False)
    last_used_at = Column(String, default="")
    usage_count = Column(Integer, default=0)
    status = Column(String, default="active")
    task_hash = Column(String, default="")
    created_at = Column(String, default="")
    updated_at = Column(String, default="")
