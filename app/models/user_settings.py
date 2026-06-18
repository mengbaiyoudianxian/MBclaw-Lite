from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True)
    approval_threshold = Column(Float, default=0.45)
    approval_level = Column(String, default="medium")
    updated_at = Column(String, default="")
