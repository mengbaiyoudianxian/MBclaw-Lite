# MBclaw-Lite / Core

> **仓库定位**：MBclaw 生产代码仓库（Core）。
> 只接受**已确认可执行的设计**、**已落地功能**、**OpenHands 可直接实施的任务**。
> 设计文档与未验证方案 → [MBclaw](https://github.com/mengbaiyoudianxian/MBclaw)。
> 否决方案与失败实验 → [MBclaw-Memory](https://github.com/mengbaiyoudianxian/MBclaw-Memory)。

---

## ⚠️ R0 冻结期（2026-06-21 起）

本仓库**冻结新增功能**，进入收敛重构期。详见：
- 现状审计：[MBclaw/design/audit/AUDIT-2026-06-21.md](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/audit/AUDIT-2026-06-21.md)
- 新 MVP 定义：[MBclaw/design/mvp/MVP-v2.md](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/mvp/MVP-v2.md)
- 收敛路线图：[MBclaw/design/roadmap/ROADMAP-v2.md](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/ROADMAP-v2.md)

**R0 期内只接受**：
1. 把指定 services 物理迁出 Core（清单：[MBclaw-Memory/drafts/2026-06-21_legacy-services-to-be-extracted.md](https://github.com/mengbaiyoudianxian/MBclaw-Memory/blob/main/drafts/2026-06-21_legacy-services-to-be-extracted.md)）
2. Bug 修复
3. 测试补强

**拒绝**：任何新特性、新服务、新模型。

---

## 当前快照（审计时点）

| 指标 | 当前 | R1 目标 |
|---|---|---|
| 代码行 (`app/`) | 10379 | < 3000 |
| Services | 39 | 7 |
| Routers | 27 | 8 |
| Models | 24 | 8 |
| Tests | 102（单文件） | 80+（分层） |

R1 完成定义见 `MVP-v2.md §2`。

---

## 技术栈（不变）

- Python 3.10+ / FastAPI / SQLAlchemy 2.0 / SQLite (WAL+FTS5) / jieba
- LLM：API Only（不本地跑模型）

## 启动

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 LLM API key
uvicorn app.main:app --reload
```

## 三仓库分流（CTO 规则）

| 输出类型 | 去哪里 |
|---|---|
| 可运行代码、已验证功能 | **本仓库（Core）** |
| 架构、规划、未验证方案 | [MBclaw](https://github.com/mengbaiyoudianxian/MBclaw) |
| 否决方案、失败实验、灵感草稿 | [MBclaw-Memory](https://github.com/mengbaiyoudianxian/MBclaw-Memory) |

> 不允许直接混合输出。不确定的内容默认进 Design，不允许进 Core。
