# T4.1 — 由 OpenHands 实现。
# 约束: ≤80 行
# 必含:
#   def close_session(db, sid: int, llm) -> dict:
#       1. 加载 messages
#       2. 已 closed → 幂等返回
#       3. llm_out = llm.summarize_session(messages)
#       4. jieba TF-IDF top-10（与 llm_out.keywords 合并去重，llm 1.0 / jieba 0.5）
#       5. MemoryRepo(db).write_session_memory(...)
#       6. session.status='closed'; ended_at=now()
#       7. return {summary, keywords, experiences, stats}
# 不允许: 异步; 调方法外 service; 直 import 模型表
