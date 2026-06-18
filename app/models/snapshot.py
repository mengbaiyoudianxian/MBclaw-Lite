from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    path = Column(String, default="")
    reason = Column(String, default="")
    trigger_rule = Column(String, default="")
    content_json = Column(Text, default="")
    created_at = Column(String, default="")
