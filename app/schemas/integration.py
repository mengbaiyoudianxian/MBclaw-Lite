from pydantic import BaseModel, ConfigDict


class IntegrationCreate(BaseModel):
    provider: str
    display_name: str = ""
    api_key: str = ""
    base_url: str = ""
    config: dict = {}


class IntegrationOut(BaseModel):
    id: int
    provider: str
    display_name: str
    api_key: str
    base_url: str
    config: str
    status: str
    free_trial_expiry: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)
