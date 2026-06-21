# T2.1 — 由 OpenHands 实现。
# 约束: ≤120 行
# 必含:
#   class LLMOutput(pydantic.BaseModel):
#       summary: str = Field(max_length=400)
#       keywords: list[str] = Field(max_length=10)
#       experiences: list[Experience] = Field(max_length=5)
#   class LLMClient:
#       def __init__(self, base_url, api_key, model): ...
#       def summarize_session(self, messages: list[dict]) -> LLMOutput
# Prompt 模板写死（见 DEV-PLAN-r0 §1 T2.1）
# response_format={"type":"json_object"}, 失败重试 1 次
# 不允许: MiMo 特殊路径; 调业务模块; 多 prompt 模板
