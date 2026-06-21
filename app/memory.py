# T3.1-T3.4 — 由 OpenHands 实现。
# 约束: 整文件 ≤200 行
# 必含:
#   class MemoryHit(BaseModel):
#       session_id: int; summary: str; keywords: list[str]; score: float
#   class MemoryRepo:
#       def __init__(self, db_session): ...
#       def write_session_memory(self, sid, summary, keywords, experiences) -> None  # T3.1
#       def query(self, q: str, top_n: int = 3) -> list[MemoryHit]                   # T3.2
#       def query_experiences(self, q, top_n: int = 2) -> list                       # T3.3
#       def render_injection_for_new_session(self, exclude_sid) -> str | None        # T3.3
#       def _maybe_evict_experiences(self) -> int                                    # T3.4
# 不允许: 调 LLM; 接 HTTP; 注入超 800; 后台定时
