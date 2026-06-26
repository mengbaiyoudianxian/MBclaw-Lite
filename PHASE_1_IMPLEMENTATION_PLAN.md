# MBclaw Memory System v1 — Phase 1 实施方案

> 版本: v1.0  
> 日期: 2026-06-25  
> 前提: Memory System v0.5 的 Summary 管线继续运行，新 Memory System 并行写入

---

## 一、Workspace 实现方案

### 1.1 概念

Workspace 是记忆隔离边界。不同项目（如"数据库设计"、"MBclaw开发"）的记忆互不污染。

### 1.2 数据模型

```sql
CREATE TABLE workspaces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,           -- 用户可见名称
    topic       TEXT,                    -- 一句话描述
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    is_archived INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX idx_workspace_name ON workspaces(name);
```

### 1.3 WorkspaceManager 接口

```python
# app/workspace/manager.py

class WorkspaceManager:
    """工作区管理器"""

    def __init__(self, db: Session)

    def create(self, name: str, topic: str = "") -> Workspace
    def get(self, ws_id: int) -> Workspace | None
    def get_or_create_default(self) -> Workspace
    def list_active(self) -> list[Workspace]
    def get_context(self, ws_id: int) -> WorkspaceContext
    def archive(self, ws_id: int)
```

### 1.4 Session 与 Workspace 关联

在现有 `sessions` 表加一列：

```sql
ALTER TABLE sessions ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
```

- `workspace_id = NULL` → 属于默认工作区（向后兼容）
- 新建 session 时 API 传入 `workspace_id`
- 旧 API 不带 workspace_id 的请求自动分配到默认工作区

---

## 二、Memory 统一表设计

### 2.1 完全 DDL

```sql
CREATE TABLE memory (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id      INTEGER NOT NULL REFERENCES workspaces(id),
    session_id        INTEGER REFERENCES sessions(id),
    type              TEXT NOT NULL CHECK(type IN ('episode','semantic','procedure','failure')),
    content_json      TEXT NOT NULL,          -- JSON: {goal, decision, result, tags, ...}
    embedding         BLOB,                  -- float32数组的二进制存储
    importance_score  REAL NOT NULL DEFAULT 0.5,  -- 0.0~1.0, 越高越重要
    tags              TEXT,                  -- JSON array: ["tag1","tag2"]
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at      TEXT,
    usage_count       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_memory_ws_type ON memory(workspace_id, type);
CREATE INDEX idx_memory_ws_importance ON memory(workspace_id, importance_score DESC);
CREATE INDEX idx_memory_ws_lastused ON memory(workspace_id, last_used_at DESC);
```

### 2.2 五种 type 的 content_json 结构

| type | content_json | 示例 |
|------|-------------|------|
| `episode` | `{goal, decision, result, context}` | "用户想优化数据库→选了WAL模式→查询快3倍→背景:SQLite性能瓶颈" |
| `semantic` | `{topic, facts:[]}` | "MBclaw后端用FastAPI+SQLite, 部署在47.83.2.188" |
| `procedure` | `{task, steps:[], prerequisites:[], expected_outcome}` | "加API端点: 1.定义pydantic model 2.写路由 3.注册到main.py→编译通过" |
| `failure` | `{task, attempt, why_failed, lesson}` | "用了ChromaDB向量库→文件锁冲突→应该用SQLite BLOB存embedding" |

### 2.3 为什么一张表而不是四张表

- **统一检索**: 跨type搜索只需查一张表
- **统一排序**: importance_score + embedding相似度统一打分
- **统一索引**: 一个FTS5虚拟表覆盖所有type
- **简化MemoryRepo**: 一张表的CRUD vs 四张表的联合查询

---

## 三、Embedding 存储方案

### 3.1 为什么不用向量数据库

- R0 铁律: 禁止加依赖（ChromaDB/Milvus/Qdrant全部禁止）
- SQLite BLOB 存 float32 数组，Python numpy 算余弦相似度
- 1000条 memory × 1536维 × 4字节 = 6MB，完全在SQLite能力范围内

### 3.2 存储格式

```python
import struct, numpy as np

def encode_embedding(vec: list[float]) -> bytes:
    """float32列表 → BLOB"""
    return struct.pack(f'{len(vec)}f', *vec)

def decode_embedding(blob: bytes) -> np.ndarray:
    """BLOB → numpy数组"""
    return np.frombuffer(blob, dtype=np.float32)
```

### 3.3 Embedding API

```python
# app/llm.py 新增方法

class LLMClient:
    def embed(self, text: str) -> list[float]:
        """调用 embedding API (如 text-embedding-3-small)
        返回 1536维 float32 向量
        """
        # POST /v1/embeddings
        # input=text, model=text-embedding-3-small
```

**环境变量**: `MBCLAW_EMBEDDING_API_KEY`, `MBCLAW_EMBEDDING_BASE_URL`, `MBCLAW_EMBEDDING_MODEL`

### 3.4 检索算法

```python
# app/memory/retrieval.py

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search_by_embedding(query_vec: np.ndarray, memories: list[Memory], top_k: int = 10) -> list[tuple[Memory, float]]:
    """余弦相似度检索, 返回 (memory, score) 排序列表"""
    scored = [(m, cosine_similarity(query_vec, decode_embedding(m.embedding)))
              for m in memories if m.embedding is not None]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
```

### 3.5 Embedding 生成时机

会话关闭时:
```
close_session → load messages → llm.embed(full_text) → 得到query_vec
              → llm.summarize_session() → 得到summary+keywords+experiences (旧管线，继续运行)
              → MemoryEncoder.encode() → 产出4种type的memory
              → llm.embed(memory_text) → 每条memory单独embedding
              → MemoryRepo.write(memory with embedding) → 写入新memory表
```

---

## 四、Memory Encoder 输出结构

### 4.1 Encoder 接口

```python
# app/memory/encoder.py

class MemoryEncoder:
    """记忆编码器 — LLM驱动, 结构化提取+分类+评分"""

    def __init__(self, llm: LLMClient)

    def encode(self, messages: list[dict], workspace_id: int) -> EncodeResult:
        """输入对话消息列表, 输出结构化记忆"""

class EncodeResult:
    episodes:   list[EpisodeMemory]    # 0~3条
    semantics:  list[SemanticMemory]   # 0~3条
    procedures: list[ProcedureMemory]  # 0~2条
    failures:   list[FailureMemory]    # 0~2条
```

### 4.2 LLM Prompt 结构

```
你是记忆编码器。分析以下对话，提取结构化记忆。

对话:
{conversation_text}

请按以下格式输出JSON:

{
  "episodes": [
    {"goal": "用户想做什么", "decision": "做了什么决定", "result": "结果如何", "tags": ["tag1"]}
  ],
  "semantics": [
    {"topic": "知识主题", "facts": ["事实1", "事实2"], "tags": ["tag1"]}
  ],
  "procedures": [
    {"task": "任务名", "steps": ["步骤1", "步骤2"], "prerequisites": ["前置条件"], "expected_outcome": "预期结果", "tags": ["tag1"]}
  ],
  "failures": [
    {"task": "尝试了什么", "attempt": "具体怎么做", "why_failed": "为什么失败", "lesson": "教训", "tags": ["tag1"]}
  ]
}

规则:
- 每种类型最多3条
- 如果对话中没有对应类型,返回空数组
- tags用中文, 2~5个
- 只提取有价值的、未来可能复用的信息
```

### 4.3 每条 memory 的最终 content_json 格式

```json
// episode
{"goal":"优化数据库性能","decision":"启用WAL模式","result":"写入速度提升3倍","tags":["SQLite","性能优化","WAL"]}

// semantic
{"topic":"MBclaw技术栈","facts":["FastAPI 0.115","SQLAlchemy 2.0","SQLite WAL+FTS5","jieba分词"],"tags":["技术栈","后端"]}

// procedure
{"task":"创建API端点","steps":["1. 定义Pydantic请求模型","2. 在api.py写路由函数","3. 注册到main.py router"],"prerequisites":["已有数据模型"],"expected_outcome":"端点可接受HTTP请求并返回JSON","tags":["API","FastAPI","开发流程"]}

// failure
{"task":"语义搜索","attempt":"安装ChromaDB做向量检索","why_failed":"ChromaDB在测试环境出现文件锁冲突,无法同时多进程访问","lesson":"SQLite BLOB存储embedding+Python余弦相似度足够用,不需要单独向量数据库","tags":["向量搜索","ChromaDB","过度工程"]}
```

---

## 五、Importance Score 设计

### 5.1 初始评分（MemoryEncoder 产出时）

| type | 初始 score | 理由 |
|------|-----------|------|
| `failure` | 0.85 | 失败教训最有价值,默认高权重 |
| `procedure` | 0.70 | 可复用方法价值高 |
| `semantic` | 0.50 | 中性知识 |
| `episode` | 0.30 | 单次事件价值最低 |

### 5.2 动态调整规则

```python
def adjust_importance(memory: Memory, event: str) -> float:
    """根据使用事件调整importance"""
    base = memory.importance_score

    match event:
        case "recalled":          # 被检索+使用 → +0.05
            base = min(1.0, base + 0.05)
        case "recalled_and_helped": # 被检索+用户确认有用 → +0.15
            base = min(1.0, base + 0.15)
        case "not_used_30d":       # 30天未使用 → -0.10
            base = max(0.05, base - 0.10)
        case "not_used_90d":       # 90天未使用 → -0.30
            base = max(0.05, base - 0.30)
        case "contradicted":       # 被新经验推翻 → -0.40
            base = max(0.05, base - 0.40)

    return base
```

### 5.3 importance_score 在检索中的使用

```python
# 最终排序分数 = embedding相似度 × 0.6 + importance_score × 0.4
def final_score(cosine_sim: float, importance: float) -> float:
    return cosine_sim * 0.6 + importance * 0.4
```

---

## 六、与旧系统并行迁移方案

### 6.1 核心原则

> 🚫 **不删除旧代码。** 旧 Summary 管线继续运行。新 Memory System 写入新 memory 表。两套系统同时产出，互不干扰。

### 6.2 并行架构

```
                    POST /session/{id}/close
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌────────────────┐             ┌────────────────┐
     │  旧管线 (保留)  │             │  新管线 (新增)  │
     │                │             │                │
     │ llm.summarize  │             │ MemoryEncoder  │
     │ → summary      │             │  .encode()     │
     │ → keywords     │             │ → episodes     │
     │ → experiences  │             │ → semantics    │
     │                │             │ → procedures   │
     │ MemoryRepo     │             │ → failures     │
     │ .write_session │             │                │
     │ (旧表)         │             │ MemoryRepo     │
     │                │             │ .write_v2()    │
     └────────────────┘             │ (新memory表)    │
                                    └────────────────┘
```

### 6.3 具体步骤

#### Step 1: 新建表（不影响旧表）

```sql
-- 新建,不删旧表
CREATE TABLE workspaces (...);
CREATE TABLE memory (...);
ALTER TABLE sessions ADD COLUMN workspace_id ...;
```

#### Step 2: 新增 API 端点（不删旧端点）

```python
# 旧端点保留不动
POST /sessions                    # 旧,继续工作
POST /sessions/{sid}/close        # 旧,继续工作
GET  /search                      # 旧,继续工作

# 新端点
POST /workspace/create            # 新
POST /workspace/{id}/session      # 新
GET  /workspace/{id}/context      # 新
POST /session/{id}/close-v2       # 新,触发MemoryEncoder
GET  /memory/search               # 新,embedding+全文搜索
```

#### Step 3: close_session 并行写入

```python
# app/pipeline.py 修改

def close_session(db, sid, llm):
    # === 旧管线 (不动) ===
    # ... 原来的 llm.summarize_session() + MemoryRepo.write_session_memory() 全部保留 ...
    old_result = _close_session_old(db, sid, llm)

    # === 新管线 (新增) ===
    try:
        encoder = MemoryEncoder(llm)
        result = encoder.encode(all_messages, workspace_id)
        memory_repo.write_v2(result, workspace_id, sid)
        new_result = {"memory_count": result.total_count}
    except Exception as e:
        log.warning(f"新管线写入失败(不影响旧管线): {e}")
        new_result = {"error": str(e)}

    return {**old_result, "memory_v2": new_result}
```

#### Step 4: 验证脚本

```python
# tests/e2e/test_parallel_pipelines.py

def test_both_pipelines_produce_output():
    """两套管线同时产出，互不影响"""
    # 1. 创建workspace
    # 2. 创建session并发送消息
    # 3. close session
    # 4. 验证旧表: summaries/keywords/experiences 有数据
    # 5. 验证新表: memory 有数据(至少1条)
    # 6. 验证旧API /search 仍然正常工作
    # 7. 验证新API /memory/search 返回结果
```

### 6.4 切换策略

| 阶段 | 旧管线 | 新管线 | 触发条件 |
|------|--------|--------|---------|
| 当前 (v0.5) | ✅ 唯一 | ❌ 不存在 | - |
| Phase 1 实施中 | ✅ 主 | ✅ 并行(静默) | 每次close都跑 |
| Phase 1 验证后 | ✅ 保留 | ✅ 主检索 | 新API用新管线, 旧API继续旧管线 |
| Phase 2 (未来) | ⬜ 可删 | ✅ 唯一 | 新管线稳定90天+所有测试通过 |

---

## 七、新增文件清单

```
app/
├── workspace/
│   ├── __init__.py
│   └── manager.py          # WorkspaceManager (~80行)
├── memory/
│   ├── __init__.py
│   ├── encoder.py           # MemoryEncoder (~120行)
│   └── retrieval.py         # 多策略检索 (~100行)
├── context/
│   ├── __init__.py
│   └── builder.py           # ContextBuilder (~80行)
├── api.py                   # 修改: 加5个新端点 (~+80行)
├── models.py                # 修改: 加Workspace/Memory ORM (~+60行)
├── pipeline.py              # 修改: 加并行写入 (~+30行)
├── db.py                    # 修改: init_db加新表 (~+5行)
└── llm.py                   # 修改: 加embed()方法 (~+30行)
```

新增约 **485 行**，修改约 **205 行**，总计约 **690 行增量**。加上现有 1341 行 = **2031 行**（仍远低于审计前 10379 行的膨胀规模）。

---

## 八、Phase 1 实施优先级

| 顺序 | 任务 | 预估时间 | 产出 |
|------|------|---------|------|
| 1 | 新建 workspace/memory 表 + models.py 更新 | 30min | DDL + ORM |
| 2 | llm.py 加 embed() | 30min | embedding API调用 |
| 3 | WorkspaceManager | 1h | workspace CRUD |
| 4 | MemoryEncoder | 2h | 结构化提取+分类+importance |
| 5 | MemoryRepo重写(v2) | 2h | 统一写入+检索+embedding存取 |
| 6 | MemoryRetrieval | 1.5h | 多策略检索+打分排序 |
| 7 | ContextBuilder | 1h | workspace级上下文构建 |
| 8 | api.py 新端点 | 1h | 5个新API |
| 9 | pipeline.py 并行写入 | 30min | 新旧管线并行 |
| 10 | 测试 + 验证脚本 | 2h | e2e + unit tests |
| **总计** | | **~11.5h** | Memory System v1 可运行 |

---

## 九、不做的事情（明确禁止）

- ❌ 不删除旧 Summary 管线
- ❌ 不引入 ChromaDB/Milvus/任何向量数据库
- ❌ 不引入 langchain/llamaindex
- ❌ 不做多 Agent
- ❌ 不做异步队列/Celery
- ❌ 不修改 tests/e2e/test_memory_loop.py 的现有断言

---

## 十、验收标准

1. ✅ 旧 `/search` API 仍然正常工作
2. ✅ 旧 `test_memory_loop.py` e2e 测试全绿
3. ✅ 新 `/memory/search?q=数据库` 返回 embedding + FTS5 混合结果
4. ✅ 新 `/workspace/create` 创建独立工作区
5. ✅ 工作区A的记忆不会出现在工作区B的检索结果中
6. ✅ failure memory 的 importance_score > episode memory
7. ✅ embedding 生成+存储+检索全链路可运行
