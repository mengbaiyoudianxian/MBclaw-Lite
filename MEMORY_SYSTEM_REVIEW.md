# MBclaw Memory System v1 — 架构审查报告

> 审查日期: 2026-06-25  
> 审查范围: MBclaw 全仓库（MBclaw/design + MBclaw-Lite/core + MBclaw-Memory/meta + MBclaw-workspace）  
> 审查目的: 确定 Memory System v1 的真实实施方案，明确保留/删除/新建

---

## 一、当前架构分析

### 1.1 现有模块清单（MBclaw-Lite r0 分支）

| # | 文件 | 行数 | 作用 | 记忆力相关性 |
|---|------|------|------|-------------|
| 1 | `app/main.py` | ~30 | FastAPI 入口, CORS, /health | 间接 |
| 2 | `app/db.py` | 61 | SQLite+WAL, SQLAlchemy引擎, PRAGMA, 建表 | 基础层 |
| 3 | `app/models.py` | 109 | 7个ORM模型(Session/Message/Summary/Keyword/Experience/Tool/ModelProfile) | **核心** |
| 4 | `app/llm.py` | 114 | OpenAI兼容LLM客户端, summarize_session() | **直接** |
| 5 | `app/memory.py` | 193 | MemoryRepo — 双召回(FTS5+jieba) + 写入 + 注入 + 淘汰 | **核心** |
| 6 | `app/pipeline.py` | 75 | close_session() — 编排LLM摘要→MemoryRepo持久化 | **直接** |
| 7 | `app/api.py` | 266 | 12个REST端点(sessions/messages/search/agent/tools/providers) | **直接** |
| 8 | `app/tools.py` | 256 | 18个内置工具(文件/shell/记忆/网络/浏览器等) | 间接 |
| 9 | `app/providers.py` | ~80 | 多LLM提供商调度 | 间接 |
| 10 | `app/agent.py` | 127 | Agent循环(LLM↔工具执行) | 间接 |
| 11 | `app/schema/fts.sql` | ~30 | FTS5虚拟表+6个触发器 | **直接** |

**总计: ~1341行 Python (预算1500以内)**

### 1.2 当前记忆数据模型

```
sessions    — id, title, status(active/closed), started_at, ended_at
messages    — id, session_id(FK), role, content, created_at
summaries   — id, session_id(FK,UNIQUE), summary(text), created_at
keywords    — id, session_id(FK), keyword, weight
experiences — id, session_id(FK), kind(success/failure/lesson), title, content, keywords_json, last_recalled_at, recall_count
```

FTS5虚拟表:
```
messages_fts    — ON messages.content (unicode61)
experiences_fts — ON experiences.title + experiences.content (unicode61)
```

### 1.3 当前记忆数据流

```
用户对话 → POST /sessions/{sid}/messages → 记录消息
         → POST /sessions/{sid}/close
                → pipeline.close_session()
                   → llm.summarize_session() → 产出 summary + keywords + 0~5 experiences
                   → jieba TF-IDF → 补充关键词
                   → MemoryRepo.write_session_memory() → 写入 summaries/keywords/experiences表
                   → 标记 session.status=closed
         
新会话 → POST /sessions
                → MemoryRepo.render_injection_for_new_session()
                   → FTS5召回 summaries + experiences
                   → 加权排序 → 渲染 ≤800字符 system message
                   → 注入到新会话的第一条 system message
```

### 1.4 依赖关系

```
api.py ───────────── 入口层
  ├─ pipeline.py ─── 编排层
  │   ├─ llm.py ──── LLM调用
  │   └─ memory.py ─ 记忆仓储(核心)
  │       └─ models.py
  ├─ agent.py ────── Agent运行时
  │   ├─ memory.py
  │   └─ tools.py
  ├─ tools.py ────── 工具系统
  └─ providers.py ── LLM调度

db.py ────────────── 基础设施
  └─ models.py
```

**方向正确**: 单向依赖, MemoryRepo是唯一记忆抽象, 符合ARCH-r0设计。

---

## 二、与 Memory System v1 规格的差距分析

### 2.1 缺少什么

| 能力 | 规格要求 | 当前状态 | 差距 |
|------|---------|---------|------|
| **Workspace隔离** | 不同项目互不污染 | ❌ 不存在 | 无workspace表/API/Manager |
| **Episodic Memory** | 记住发生过的"事件" | ⚠️ 部分 | messages+summaries=事件记录, 但无结构化事件提取(goal/decision/result) |
| **Semantic Memory** | 记住稳定的"知识" | ❌ 不存在 | Experience表只有 success/failure/lesson 三种kind, 无semantic类型 |
| **Procedural Memory** | 记住可复用的"方法" | ❌ 不存在 | 无procedure类型, 无步骤/前置条件/预期结果 |
| **Failure Memory** | 记住失败案例 | ⚠️ 部分 | Experience(kind='failure')存在, 但无权重boost、无自动避开逻辑 |
| **Embedding检索** | 语义相似度搜索 | ❌ 不存在 | 只有FTS5全文+jieba关键词, 无语义向量 |
| **多策略检索** | embedding+tag+failure_boost | ❌ 不存在 | 只有FTS5+jieba双召回 |
| **记忆使用统计** | usage_count, last_used | ❌ 不存在 | Experience表无这些字段 |
| **遗忘机制** | 30天降权/90天冷存 | ❌ 不存在 | 只有>1000条时的硬淘汰, 无时间维度 |
| **Failure强化** | 失败记忆权重+30% | ❌ 不存在 | 无boost机制 |
| **记忆更新** | 重复问题更新旧经验 | ❌ 不存在 | 每次关闭会话追加新行 |
| **Memory Encoder** | 结构化提取 goal/decision/result/tags | ❌ 不存在 | LLM输出summary+keywords+experiences, 无结构化encoder |
| **Context Builder** | workspace级别上下文构建 | ⚠️ 部分 | render_injection只取最近一个closed session, 不跨session |

### 2.2 多余什么

| 模块 | 问题 | 建议 |
|------|------|------|
| `app/tools.py` (256行) | 18个工具远超记忆MVP需要 | **移出** → 放到 `MBclaw-Memory/drafts/legacy/` |
| `app/providers.py` | 多LLM调度非记忆核心 | **保留但冻结** — 只有1个LLM就够了 |
| `app/agent.py` (127行) | R0/R1不应有Agent | **移出** — 按AGENT-r0, R2再考虑 |

### 2.3 风险什么

| 风险 | 严重度 | 说明 |
|------|--------|------|
| 🔴 FTS5召回不准 | 高 | 中文分词依赖jieba精度, 复杂查询可能召回失败 |
| 🔴 无embedding=无语义理解 | 高 | "数据库设计"和"SQL schema"在FTS5下不相似 |
| 🟠 注入只有最近一个session | 中 | 无法跨多个历史会话综合注入 |
| 🟠 Experience表字段不够 | 中 | 缺少usage_count/last_used/embedding列 |
| 🟡 淘汰机制只看数量不看时间 | 低 | >1000条就淘汰, 不管是不是昨天刚存的 |

---

## 三、Memory System v1 最终架构

### 3.1 目标数据模型

```
workspace        — id, name, topic, created_at
session          — id, workspace_id(FK), title, status, created_at, ended_at
message          — id, session_id(FK), role, content, created_at
memory           — id, workspace_id(FK), session_id(FK), type(episode/semantic/procedure/failure),
                   content_json, embedding(BLOB), tags, created_at, last_used_at, usage_count
```

**5种Memory type:**

| type | 含义 | content_json结构 | 例子 |
|------|------|-----------------|------|
| `episode` | 事件记忆 | {goal, decision, result} | "用户问数据库设计→选了SQLite→成功" |
| `semantic` | 知识记忆 | {topic, facts} | "MBclaw使用FastAPI+SQLAlchemy" |
| `procedure` | 方法记忆 | {task, steps, prerequisites, outcome} | "创建API端点: 1.定义model 2.写api.py 3.测试" |
| `failure` | 失败记忆 | {task, attempt, why_failed} | "用了ChromaDB→文件锁→改用FTS5" |

### 3.2 目标数据流

```
┌─────────────────────────────────────────────────────────┐
│  SESSION LIFECYCLE                                      │
│                                                         │
│  1. POST /workspace/{id}/session → 绑定workspace        │
│  2. POST /message → 记录对话                            │
│  3. POST /session/{id}/close → 触发Memory Encoder       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  MEMORY ENCODER (会话关闭时)                             │
│                                                         │
│  4. LLM结构化提取:                                      │
│     {type, goal, decision, result, tags}                │
│  5. 分类: episode / semantic / procedure / failure       │
│  6. 生成embedding(调用embedding API)                     │
│  7. 写入 memory 表                                      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  MEMORY RETRIEVAL (新消息/新会话时)                       │
│                                                         │
│  8. embedding search (cosine相似度, top-N)               │
│  9. tag search (精确匹配)                                │
│  10. failure boost (失败记忆权重+30%)                     │
│  11. 排序: failure > procedure > semantic > episode      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  CONTEXT BUILDER (LLM调用前)                             │
│                                                         │
│  12. build_context(workspace_id, query)                 │
│      → 检索当前workspace相关memory(最多5条)              │
│      → 必须包含failure memory                           │
│      → procedure优先                                    │
│      → 注入到LLM system prompt                          │
└─────────────────────────────────────────────────────────┘
```

### 3.3 目标API端点

```
POST   /workspace/create          — 创建工作区
POST   /workspace/{id}/session    — 在workspace下创建新会话
GET    /workspace/{id}/context    — 获取workspace的注入上下文
POST   /message                   — 添加消息
POST   /session/{id}/close        — 关闭会话, 触发memory encoder
GET    /memory/search?q=&ws=      — 跨会话记忆搜索(embedding+全文)
GET    /memory/failures?ws=       — 列出workspace的失败记忆
```

### 3.4 关键设计约束

1. **MemoryRepo仍然是唯一记忆抽象** — 所有记忆操作通过MemoryRepo, 不直接操作memory表
2. **MemoryRepo不调LLM** — pipeline负责编排LLM调用, MemoryRepo只负责读写
3. **注入≤800字符** — 保持R0约束, context builder产出≤800字符system message
4. **无向量数据库** — embedding存SQLite BLOB, cosine相似度用Python算, 不装ChromaDB/Milvus
5. **无Agent** — R0/R1不装Agent, 所有记忆操作是同步函数调用
6. **同步管线** — session close → encoder → embedding → write, 全同步, 无队列

---

## 四、开发顺序

### 🔴 Phase 0: 清理（必须先做）

| # | 任务 | 说明 |
|---|------|------|
| P0.1 | 移出 `app/tools.py` → `MBclaw-Memory/drafts/legacy/` | 18个工具不是记忆MVP |
| P0.2 | 移出 `app/agent.py` → `MBclaw-Memory/drafts/legacy/` | R0/R1不用Agent |
| P0.3 | 移出 `app/providers.py` → 保留1个LLM入口 | 简化为单LLM调用 |
| P0.4 | 删除旧 summary/keyword 逻辑(但保留表结构作为过渡) | 为新的统一memory表让路 |
| P0.5 | 统一目录结构: app/api/ app/core/ app/memory/ app/workspace/ app/llm/ app/db/ | 按功能分包 |

### 🟠 Phase 1: 基础重构（应该后做）

| # | 任务 | 说明 |
|---|------|------|
| P1.1 | 新建 migration — workspace表 + memory表(含embedding BLOB) | 替代旧的summaries+keywords+experiences三表 |
| P1.2 | 实现 WorkspaceManager — create/switch/get_context | 核心隔离 |
| P1.3 | 重写 MemoryRepo — 4种type + embedding存储 + 多策略检索 | 核心仓储 |
| P1.4 | 实现 MemoryEncoder — LLM结构化提取 + 分类 + 生成embedding | 核心编码 |
| P1.5 | 实现 ContextBuilder — workspace级上下文构建, failure优先 | 核心注入 |

### 🟡 Phase 2: 强化（未来再做）

| # | 任务 | 说明 |
|---|------|------|
| P2.1 | embedding检索 (cosine相似度) | 语义搜索 |
| P2.2 | failure boost — 失败记忆权重+30% | 失败学习 |
| P2.3 | 使用统计 — usage_count + last_used_at | 热度排序 |
| P2.4 | 遗忘机制 — 30天降权 / 90天冷存 | 记忆管理 |
| P2.5 | 记忆更新 — 重复问题更新旧经验而非追加 | 去重 |

### 🟢 Phase 3: 进阶（远期）

| # | 任务 | 说明 |
|---|------|------|
| P3.1 | K2 Executor接入 (仅当memory系统稳定后) | LLM自演化 |
| P3.2 | 向量数据库(仅当SQLite BLOB性能不足时) | 可选升级 |
| P3.3 | 多模型调度 | 可选升级 |

---

## 五、保留/删除/新建清单

### ✅ 保留（不动）

| 文件 | 理由 |
|------|------|
| `app/db.py` | SQLite基础设施, 修改有限(加新表) |
| `app/models.py` | 需重构(删Tool/ModelProfile, 加Workspace/Memory), 但框架保留 |
| `app/llm.py` | LLM客户端, 需扩展summarize_session→encode_session |
| `app/memory.py` | MemoryRepo核心, 需重写但概念保留 |
| `app/pipeline.py` | 编排逻辑, 需适配新encoder |
| `app/main.py` | FastAPI入口, 几乎不动 |
| `app/api.py` | REST端点, 需适配新路由 |
| `app/schema/fts.sql` | FTS5触发器, 需更新适配新memory表 |
| `tests/` | 测试框架保留, 需更新用例 |

### ❌ 删除（移出Core）

| 文件 | 去向 |
|------|------|
| `app/tools.py` | → `MBclaw-Memory/drafts/legacy/` |
| `app/agent.py` | → `MBclaw-Memory/drafts/legacy/` |
| `app/providers.py` | → 简化合并到llm.py, 原文件移出 |

### 🆕 新建

| 文件 | 作用 |
|------|------|
| `app/workspace/manager.py` | WorkspaceManager — create/switch/get_context |
| `app/memory/encoder.py` | MemoryEncoder — LLM结构化提取+分类+embedding |
| `app/memory/retrieval.py` | MemoryRetrieval — 多策略检索(embedding+tag+failure_boost) |
| `app/context/builder.py` | ContextBuilder — workspace级上下文构建 |

---

## 六、数据库迁移计划

### 旧表 → 新表

| 旧表 | 处置 |
|------|------|
| `sessions` | 保留, 加 `workspace_id` FK |
| `messages` | 保留不动 |
| `summaries` | **删除** — 合并到 `memory` 表(type=episode/semantic) |
| `keywords` | **删除** — tags字段存入 `memory` 表 |
| `experiences` | **删除** — 合并到 `memory` 表(type=procedure/failure) |
| `tools` | **删除** — 移出Core |
| `model_profiles` | **删除** — 移出Core |

### 新表

| 新表 | 关键字段 |
|------|---------|
| `workspaces` | id, name, topic, created_at |
| `memory` | id, workspace_id, session_id, type(enum), content_json, embedding(BLOB), tags, created_at, last_used_at, usage_count |

### FTS5适配

```
memory_fts — ON memory.content_json (提取text部分)
```

---

## 七、结论

### 当前属于什么阶段

**MBclaw-Lite r0 = Memory System v0.5**

- ✅ 有闭合的记忆管线 (session close → summarize → write → retrieve → inject)
- ✅ 有统一MemoryRepo抽象
- ✅ 有FTS5+jieba双召回
- ✅ 有端到端测试验证
- ❌ 无Workspace隔离
- ❌ 无embedding语义搜索
- ❌ 无4种memory type分类
- ❌ 无使用统计/遗忘机制
- ❌ 有多余模块 (tools, agent, providers)

### 实现 Memory System v1 需要

1. **Phrase 0 清理** — 移出3个非核心模块, 统一目录结构 (~2小时)
2. **Phrase 1 重构** — workspace表+memory表+MemoryRepo重写+encoder+context builder (~1天)
3. **Phrase 2 强化** — embedding检索+failure boost+使用统计 (~1天)

### 一句总结

> 当前代码基础扎实(MemoryRepo抽象+FTS5管线), 但缺Workspace隔离、4种memory type分类、embedding检索三大核心能力。Phase 0清理+Phase 1重构后可达到Memory System v1规格。
