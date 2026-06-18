from pydantic import BaseModel, ConfigDict


class SkillCardCreate(BaseModel):
    name: str
    trigger_condition: str = ""
    steps: list[str] = []
    known_pitfalls: list[str] = []
    category: str = ""
    pinned: bool = False


class SkillCardUpdate(BaseModel):
    name: str | None = None
    trigger_condition: str | None = None
    steps: list[str] | None = None
    known_pitfalls: list[str] | None = None
    category: str | None = None
    pinned: bool | None = None
    status: str | None = None


class SkillCardOut(BaseModel):
    id: int
    name: str
    trigger_condition: str
    steps: str
    known_pitfalls: str
    category: str
    created_by: str
    pinned: bool
    last_used_at: str
    usage_count: int
    status: str
    task_hash: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class BatchMemoryRequest(BaseModel):
    target: str  # "memory" or "user"
    operations: list[dict]  # [{action, entry/old/new}]


class MemoryEntryWrite(BaseModel):
    target: str  # "memory" or "user"
    entry: str
