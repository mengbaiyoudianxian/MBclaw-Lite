# T5.1 — 由 OpenHands 实现。
# 约束: ≤300 行
# 必含 5 端点（详见 DEV-PLAN-r0 §1 T5.1）:
#   POST   /sessions                 → 建 + 注入
#   POST   /sessions/{sid}/messages  → 写 + JSONL
#   POST   /sessions/{sid}/close     → pipeline.close_session
#   GET    /sessions/{sid}/messages
#   GET    /search?q=&limit=
# 不允许: 加端点; 管理后台; 鉴权（R0 单用户硬编码）
# 不允许: from app.models import (Summary|Keyword|Experience)  (CI 拦截)
