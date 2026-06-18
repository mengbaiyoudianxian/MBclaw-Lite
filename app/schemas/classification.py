from pydantic import BaseModel, ConfigDict


class ClassificationNodeBase(BaseModel):
    parent_id: int | None = None
    level: int = 1
    category_name: str
    summary_short: str = ""
    summary_detailed: str = ""
    failed_approaches: str = "[]"
    keywords: str = "[]"


class ClassificationNodeCreate(ClassificationNodeBase):
    session_id: int | None = None


class ClassificationNodeOut(ClassificationNodeBase):
    id: int
    project_id: int
    session_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextSearchRequest(BaseModel):
    query_text: str
    max_tokens: int = 2000
    include_failed: bool = True
