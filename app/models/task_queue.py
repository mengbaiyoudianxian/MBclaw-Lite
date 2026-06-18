from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base


class BackgroundTask(Base):
    """A task that can be suspended/resumed. Stores checkpoint for recovery.

    active_task: the task currently running (at most 1 per project)
    background_tasks: suspended tasks awaiting resumption
    """
    __tablename__ = "background_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    session_id = Column(Integer, nullable=True)
    name = Column(String, default="")
    status = Column(String, default="pending")
    # pending → active → suspended → resumed → completed / failed
    priority = Column(Integer, default=0)
    progress = Column(Float, default=0.0)
    checkpoint_json = Column(Text, default="{}")
    error_message = Column(Text, default="")
    tool_call_count = Column(Integer, default=0)
    created_at = Column(String, default="")
    updated_at = Column(String, default="")
