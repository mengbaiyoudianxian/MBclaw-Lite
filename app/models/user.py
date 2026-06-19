from datetime import datetime
from sqlalchemy import Column, Integer, String
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    external_id = Column(String, default="")
    platform = Column(String, default="")
    created_at = Column(String, nullable=False, default=lambda: datetime.now().isoformat())
