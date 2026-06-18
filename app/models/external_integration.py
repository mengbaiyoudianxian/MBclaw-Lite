from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class ExternalIntegration(Base):
    __tablename__ = "external_integrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String, nullable=False)
    display_name = Column(String, default="")
    api_key = Column(Text, default="")
    base_url = Column(String, default="")
    config = Column(Text, default="{}")
    status = Column(String, default="inactive")
    free_trial_expiry = Column(String, default="")
    created_at = Column(String, default="")
    updated_at = Column(String, default="")
