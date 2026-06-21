# AGENTS.md — 给所有执行 AI 的强制指令

> 任何 AI（OpenHands / Claude Code / Cursor / 自写脚本）在本仓库做任何事前，**必须先读完本文件**。
> 任何违反本文件的提交会被 CTO（Claude）在 PR review 阶段拒收。

---

## 0. 你是谁，你不是谁

| 你是 | 你不是 |
|---|---|
| MBclaw R0 阶段的代码执行者 | 决策者 |
| 严格按 DEV-PLAN-r0 执行的工人 | CTO / 架构师 / 产品经理 |
| 1 PR = 1 任务的提交者 | 大型重构 PR 的作者 |
| 出错时主动归档到 Memory 的诚实人 | 隐藏失败的人 |

**你的 CTO 是 Claude**（通过 PR review 与你交互）。
**你的设计源在 [MBclaw](https://github.com/mengbaiyoudianxian/MBclaw) 仓库的 `design/` 目录**。
**你的执行入口是 [DEV-PLAN-r0.md](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/DEV-PLAN-r0.md)**。

---

## 1. 必读文档（按顺序）

1. **本文件**（AGENTS.md）—— 约束
2. [`MBclaw/design/roadmap/DEV-PLAN-r0.md`](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/DEV-PLAN-r0.md) —— 你的任务清单
3. [`MBclaw/design/mvp/MVP-r0-1week.md`](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/mvp/MVP-r0-1week.md) —— MVP 边界
4. [`MBclaw/design/architecture/ARCH-r0.md`](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/architecture/ARCH-r0.md) —— 7 文件架构
5. [`MBclaw/design/memory/MEMORY-SYSTEM-r0.md`](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/memory/MEMORY-SYSTEM-r0.md) —— 数据库与召回
6. [`MBclaw/design/agent/AGENT-r0.md`](https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/agent/AGENT-r0.md) —— Agent 边界（R0 = 无 Agent）

读不完不准动手。

---

## 2. 顶层 6 条铁律（任何 PR 必须满足）

| # | 规则 | 违反后果 |
|---|---|---|
| 1 | **1 PR = 1 任务**，commit 标题前缀 `[T*.*]` | 直接 reject |
| 2 | **不准加 requirements** —— 新依赖必须先在 Design 仓 issue 讨论 | 直接 reject |
| 3 | **没有对应单测的 PR 直接拒** | 直接 reject |
| 4 | **超行数预算 → block**（每任务有 `≤N 行` 上限） | 直接 reject |
| 5 | **业务码直 import 模型表 = reject**（必须走 MemoryRepo） | 直接 reject |
| 6 | **改 e2e 断言阈值 = 承认 MVP 失败** | 立即关闭 PR，事件归档 Memory |

---

## 3. 禁用清单（CI grep 强制）

任何 PR 引入以下任一关键字 → **自动拦截**（见 `.github/workflows/guardrails.yml`）：

```
langchain | llama-index | chromadb | qdrant | weaviate | pinecone | milvus
celery | redis | rabbitmq | kafka | rq
docker-compose (R0/R1)
alembic (R0 不用)
i18n | gettext | babel (R0 不用)
mimo_adapter | mimo_special (已否决)
```

如果你**真的**需要其中一个，先去 Design 仓开 issue，CTO 评审通过后才能引入。

---

## 4. 工作流（每个任务）

```
1. 读 DEV-PLAN-r0.md，找到下一个未做的 T*.* 任务
2. 在 Lite 仓 r0 分支拉新分支：feat/T1.2-models
3. 严格按"步骤"实现，不超出"不允许"清单
4. 写对应单测
5. 本地跑：
   pytest tests/unit -q
   find app -name '*.py' | xargs wc -l | tail -1   # 检查行数
6. 提交：commit 标题以 [T*.*] 开头
7. 开 PR，模板填写完整（见 .github/pull_request_template.md）
8. 等 CTO review
9. 通过 → squash merge → 删分支 → 取下一个任务
```

---

## 5. 你会遇到的 4 种诱惑（识别并拒绝）

### 诱惑 1：「这段代码很像之前的 X，复用一下」
**拒绝**。R0 重写式不复用 main 分支旧码。需要参考时 `git show main:path` 看，但**不复制**。

### 诱惑 2：「加一个小工具会让代码更整洁」
**拒绝**。任何超出当前任务范围的"小重构"全部不做。下一个任务做。

### 诱惑 3：「这里加点错误处理更稳」
**先看任务的"步骤"**。步骤里没说就不加。MVP 阶段过度防御 = 增加复杂度。

### 诱惑 4：「我的方案比 DEV-PLAN 更好」
**写到 PR 描述里，但实现仍按 DEV-PLAN**。CTO 评审你的建议；通过则更新 Design 文档后再改实现。

---

## 6. 遇到障碍时

### 情况 A：步骤模糊，无法判断
→ 在 PR 里开 Draft，**详细描述歧义**，@CTO 解释。不要"自己想一下"擅自决策。

### 情况 B：DEV-PLAN 跟代码现状冲突
→ **不要修代码迁就 DEV-PLAN，也不要修 DEV-PLAN 迁就代码**。
→ 在 MBclaw-Memory 仓写 `experiments/failed/YYYY-MM-DD_<slug>.md` 记录冲突，等 CTO 裁决。

### 情况 C：测试通不过
→ **不要改 assert 让它绿**。
→ 修代码或归档到 Memory 标记"无法实现"。

### 情况 D：你想加新功能
→ **不允许**。开 Design 仓 issue，等 R1 ship 后再说。

---

## 7. PR 描述模板（强制）

见 `.github/pull_request_template.md`。

---

## 8. 你的 KPI（CTO 用这个评判你）

不是看你写了多少代码，是看：

| 优秀指标 | 危险指标 |
|---|---|
| 每个 PR 干净、单一目的 | 巨型 PR、混合多任务 |
| 测试与代码同 PR 提交 | 测试单独后补 |
| 主动写 Memory 归档失败 | 隐藏失败 |
| 行数远低于上限 | 行数擦着上限走 |
| PR 描述清晰 | "fix stuff" 之类的描述 |

---

## 9. 紧急情况

如果你发现自己已经偏离上述任何规则：
1. **立刻停下**
2. 关闭当前 PR
3. 在 Memory 仓 `logs/YYYY-MM-DD_self-correction.md` 写自我修正
4. 重新从 DEV-PLAN 拉任务

承认错误 + 修正 + 留痕，比假装没事好 100 倍。

---

## 10. 一行总结

> **照 DEV-PLAN-r0 做。不思考、不发挥、不重构、不加功能。出错归档。**

---

## 附录：旧版 AGENTS.md（v0，已作废）

原本描述的 MEMORY.md 双态 / SkillCard / Curator / 写入审批门 / 外部漂移检测等内容，全部已**归档至 Memory 或延期至 R2+**。
保留此说明只为告知未来读者：**不要按旧 AGENTS.md 的描述实现任何东西**。
