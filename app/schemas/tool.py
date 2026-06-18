from pydantic import BaseModel, ConfigDict


class ToolCreate(BaseModel):
    name: str
    summary_100: str = ""
    tags: list[str] = []
    full_description: str = ""
    usage_examples: list[str] = []
    compatible_models: list[str] = []
    classification_node_id: int | None = None


class ToolUpdate(BaseModel):
    summary_100: str | None = None
    tags: list[str] | None = None
    full_description: str | None = None
    usage_examples: list[str] | None = None
    compatible_models: list[str] | None = None
    rating: float | None = None


class ToolOut(BaseModel):
    id: int
    name: str
    summary_100: str
    tags: str
    full_description: str
    usage_examples: str
    compatible_models: str
    classification_node_id: int | None
    rating: float
    usage_count: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ToolSearchRequest(BaseModel):
    query: str
    max_results: int = 10
    budget_tokens: int = 2000


class ToolSelectRequest(BaseModel):
    task_description: str
    budget_tokens: int = 2000
    required_tags: list[str] = []
