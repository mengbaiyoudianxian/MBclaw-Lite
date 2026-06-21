# MBclaw-Lite / Core

> **仓库定位**：MBclaw 生产代码仓库（Core）。
> 只接受**已确认可执行的设计**、**已落地功能**、**OpenHands 可直接实施的任务**。
> 设计文档与未验证方案 → [MBclaw](https://github.com/mengbaiyoudianxian/MBclaw)。
> 否决方案与失败实验 → [MBclaw-Memory](https://github.com/mengbaiyoudianxian/MBclaw-Memory)。

---

## 🔴 给所有执行 AI（必读，否则你的 PR 一定被拒）

1. **[AGENTS.md](AGENTS.md)** — 6 条铁律 + 工作流
2. **[PROMPTS-FOR-EXECUTORS.md](PROMPTS-FOR-EXECUTORS.md)** — 7 个可直接复制的提示词
3. **[.github/pull_request_template.md](.github/pull_request_template.md)** — PR 模板
4. **[.github/workflows/guardrails.yml](.github/workflows/guardrails.yml)** — CI 自动拦截（依赖/行数/直 import）

---

## 当前分支状态

| 分支 | 状态 |
|---|---|
| `main` | 旧版本（10379 行），R0 冻结，仅作历史参考 |
| **`r0`** | **新版骨架已就绪**，等 OpenHands 按 DEV-PLAN-r0 填充 |

```bash
git checkout r0
```

---

## R0 骨架（已就绪）

```
app/
├── __init__.py
├── db.py           # T1.1 (placeholder)
├── models.py       # T1.2 (placeholder)
├── schema/fts.sql  # T1.3 (placeholder)
├── llm.py          # T2.1 (placeholder)
├── memory.py       # T3.1-T3.4 (placeholder)
├── pipeline.py     # T4.1 (placeholder)
├── api.py          # T5.1 (placeholder)
└── main.py         # T5.2 (placeholder)
tests/
├── conftest.py
├── unit/
└── e2e/test_memory_loop.py  # T6.2 唯一不可妥协测试
scripts/
└── check_lines.sh  # 本地预算检查
.github/
├── pull_request_template.md
├── ISSUE_TEMPLATE/task.md
└── workflows/guardrails.yml
```

每个 placeholder 文件已写注释：任务 ID、约束、必含、不允许。OpenHands 拉到即可执行。

---

## 设计文档入口（必读）

| 文档 | 用途 |
|---|---|
| **🔥 [DEV-PLAN-r0](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/DEV-PLAN-r0.md)** | OpenHands 任务清单 |
| [SURVIVAL-REVIEW](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/audit/SURVIVAL-REVIEW-2026-06-21.md) | 项目生死评审 |
| [MVP-r0-1week](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/mvp/MVP-r0-1week.md) | MVP 边界 |
| [ARCH-r0](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/architecture/ARCH-r0.md) | 7 文件单进程架构 |
| [MEMORY-SYSTEM-r0](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/memory/MEMORY-SYSTEM-r0.md) | 数据库 + 召回 |
| [AGENT-r0](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/agent/AGENT-r0.md) | R0 = 无 Agent |

---

## 启动（仅在 r0 全部实现后）

```bash
git checkout r0
pip install -r requirements.txt
cp .env.example .env  # 填入 LLM API key
uvicorn app.main:app --reload
```

---

## 三仓库分流（CTO 规则）

| 输出类型 | 去哪里 |
|---|---|
| 可运行代码、已验证功能 | **本仓库（Core）** |
| 架构、规划、未验证方案 | [MBclaw](https://github.com/mengbaiyoudianxian/MBclaw) |
| 否决方案、失败实验、灵感草稿 | [MBclaw-Memory](https://github.com/mengbaiyoudianxian/MBclaw-Memory) |

> 不允许直接混合输出。不确定的内容默认进 Design，不允许进 Core。
