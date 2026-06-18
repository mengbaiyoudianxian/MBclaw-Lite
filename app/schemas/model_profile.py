from pydantic import BaseModel, ConfigDict


class ModelProfileCreate(BaseModel):
    key_alias: str
    model_name: str
    api_base: str = ""
    capabilities: dict[str, float] = {}
    strengths: list[str] = []
    tool_compatibility: dict[str, float] = {}
    cost_per_1k_tokens: float = 0.0
    context_window: int = 8192


class ModelRecommendRequest(BaseModel):
    task_type: str
    task_complexity: str = "medium"
    budget: float = 1.0
    required_tools: list[str] = []


class ModelProfileOut(BaseModel):
    id: int
    key_alias: str
    model_name: str
    api_base: str
    capabilities: str
    strengths: str
    tool_compatibility: str
    cost_per_1k_tokens: float
    context_window: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)
