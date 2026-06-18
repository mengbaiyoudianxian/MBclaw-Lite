# MBclaw 总体方案：借鉴 OpenClaw，从零构建完整智能体系统

## 1. OBJECTIVE

**MBclaw 不是 OpenClaw 的改装版，而是一个全新的智能体系统**——借鉴 OpenClaw 的架构思想（Agent Loop、Memory、Tool、Multi-Agent），从 MBclaw-Lite（存储层）出发，逐步构建完整的 Agent Runtime，最终达到"满血状态"：主动化智能，感知用户行为，自主介入协助。

整体路线：**MBclaw-Lite（存储层，已完工） → MBclaw-Core（Agent Runtime，新建） → MBclaw-Full（主动智能，最终形态）**

## 2. CONTEXT SUMMARY

### 2.1 当前资产：MBclaw-Lite（Phase 1+2 已完成，21/21 tests）

| 模块 | 状态 | 说明 |
|------|------|------|
| User/Project/Session/Message CRUD | ✅ 完成 | FastAPI + SQLite |
| 摘要生成 | ✅ 基础 | 规则匹配，需升级为 LLM 驱动 |
| 关键词提取 | ✅ 基础 | jieba 分词，需升级为向量 embedding |
| ProjectDNA | ✅ 基础 | 成功/失败方案、目标、工具、模型追踪 |
| 三层记忆 | ✅ 基础 | MEMORY.md + 每日笔记 + Dreams |
| JSONL 转录 | ✅ 基础 | 对话逐行记录 |
| Action 记忆 | ✅ 基础 | 权限/定时/过期 |
| 全文搜索 | ✅ 基础 | SQL LIKE |
| 快照 | ❌ 空壳 | 需实现 |

### 2.2 新架构：MBclaw 三层结构

```
┌─────────────────────────────────────────────┐
│              MBclaw-Full（最终形态）           │
│  主动智能：用户行为感知 → 自主介入 → 全自动执行  │
├─────────────────────────────────────────────┤
│            MBclaw-Core（Agent Runtime）       │
│  Agent Loop · 多Agent协作 · 工具调度 · 模型路由 │
├─────────────────────────────────────────────┤
│          MBclaw-Lite（存储层，✅已完成）        │
│  对话归档 · 分类检索 · 记忆系统 · 快照 · DNA    │
└─────────────────────────────────────────────┘
```

### 2.3 与 OpenClaw 的关系：借鉴而非 Fork

| 维度 | 借鉴 OpenClaw 的部分 | MBclaw 自己的创新 |
|------|---------------------|-------------------|
| Agent Loop | 事件驱动架构、异步消息处理 | 用户消息抢先级、后台任务不中断 |
| Memory | 三层记忆理念 | 树形分类+失败方案+向量语义搜索 |
| Tools | 工具注册/调用机制 | 三层工具索引+向量匹配+Token预算 |
| Multi-Agent | 子Agent委托 | 自主反思+共享通道+冲突协商+去重复用 |
| 模型调度 | - | 多维评分+成本感知+工具-模型联合优化 |

## 3. APPROACH OVERVIEW

**策略：先完成存储层全部能力（项目1/2/3/6/8/11/12/13），再构建 Agent Runtime（项目4/5/7/9/10），最后实现主动智能（最终构想）。**

OpenClaw 的源码作为设计参考（读其架构，不复制其代码），MBclaw 用自己的技术栈（FastAPI + asyncio + 自研 Agent Loop）独立实现。

---

## 4. IMPLEMENTATION STEPS（十三个项目逐项分析 + 最终构想）

### 🔵 STAGE A：存储层深化（在 MBclaw-Lite 现有代码上扩展）

---

### 项目一：详细日志（对话+AI思考+代码变更 全量备份）

**目标：** 每条消息不仅存 role+content，还要存 AI 的思考过程、改了什么文件、每个 transcript 文件合理分片。

**当前差距：**
- Message 模型只有 role + content
- transcript JSONL 同样只有基本字段
- 无文件分片

**方案：**
1. Message 模型加字段：`thinking_content`（TEXT）、`changed_files`（JSON，如 `[{"file": "main.py", "action": "modified", "summary": "..."}]`）
2. transcript_service 升级：每行 JSONL 包含 thinking + changed_files
3. 文件分片管理器：`TranscriptShard` 模型，按 10MB 或按 session 自动切分，旧分片自动 gzip
4. 新增 schema：`MessageCreate` 增加可选 thinking/changed_files 字段
5. 新增 API：`GET /api/sessions/{id}/transcript?include_thinking=true`

---

### 项目二：空闲时自动分析整理 → 树形分类 + 失败方案标记

**目标：** 这是 MBclaw 最核心的差异化能力。空闲时调用 LLM 对历史对话进行多层次分类，构建树形知识结构，标记失败方案，让 AI 重访项目时自动避开。

**当前差距：**
- summary_service 是纯规则匹配（关键词 if-else），无 LLM
- ProjectDNA.failed_approaches 填充极弱
- 无空闲触发机制
- 无树形分类结构

**方案：**
1. **新建 `ClassificationNode` 模型**（树形结构）：
   - `id`, `parent_id`（自引用外键）, `project_id`, `session_id`
   - `level`（1=大类, 2=细分, 3=具体话题）
   - `category_name`（如"后端→数据库→SQL优化"）
   - `summary_short`（200字粗略总结）
   - `summary_detailed`（完整详细总结）
   - `failed_approaches`（JSON：尝试了什么、为什么失败）
   - `keywords`（JSON）
   - `embedding`（向量，用于语义搜索）
2. **LLM 分类引擎** `ClassificationEngine`：
   - 输入：session 完整对话
   - 输出：结构化分类结果（level1/2/3 + summaries + failed_approaches）
   - 调用用户配置的 LLM API
3. **空闲任务调度器** `IdleTaskScheduler`：
   - 后台 asyncio task，每 N 分钟检查是否有未分类的 session
   - 逐个调用 ClassificationEngine
   - 同时也做 Dreaming 巩固
4. **失败方案注入**：AI 启动新 session 时，自动检索该分类下的所有 failed_approaches，注入 System Prompt
5. **向量搜索升级**：引入 ChromaDB（嵌入式向量数据库），替换纯 SQL LIKE 搜索

---

### 项目三：突破时自动备份快照

**目标：** 检测项目取得突破时，自动创建完整快照，防止后续修改破坏成果。

**当前差距：**
- snapshots/ 目录是空壳

**方案：**
1. **突破检测器** `BreakthroughDetector`：
   - 规则1：ProjectDNA.successful_approaches 新增条目
   - 规则2：摘要 conclusions 匹配"成功|解决|完成|突破|行了|好了"
   - 规则3：用户消息含"太好了|成功了|终于|nice"
   - 阈值：满足 ≥2 条即触发
2. **快照服务** `SnapshotService`：
   - 内容：整个 project 的 DB 行（JSON dump）+ memory 目录文件（tar.gz）
   - 存储：`snapshots/{project_name}/{timestamp}/`
   - 新增模型 `Snapshot`（id, project_id, path, reason, created_at）
3. **恢复 API**：`POST /api/projects/{id}/snapshots/{snapshot_id}/restore`
4. **手动快照 API**：`POST /api/projects/{id}/snapshots`

---

### 项目六：实时记忆预调用（对话中动态检索相关知识）

**目标：** Agent 与用户对话时，实时从存储层拉取相关历史记忆，注入上下文。

**当前差距：**
- 只有 SQL LIKE 搜索，无语义检索
- 无"根据当前对话自动检索"机制

**方案：**
1. **三层检索架构（L1→L2→L3）**：
   - **L1（关键词快速命中）**：从当前用户消息提取关键词 → SQL 查 keywords 表 → 命中则进入 L2
   - **L2（向量语义匹配）**：用当前消息的 embedding 在 ChromaDB 中搜索相似对话片段 → top K
   - **L3（详细上下文返回）**：对 L1+L2 的结果去重，返回完整对话块 + 摘要 + DNA
2. **新增 API**：`POST /api/memory/context-search`
   - 入参：`{query_text, project_id, max_tokens, include_failed}`
   - 返回：按相关性排序的历史上下文列表
3. **Token 预算控制**：返回结果总 token 数不超过 max_tokens，相关性低的截断
4. **Agent Loop 集成**：每轮对话开始前，Agent Runtime 自动调此 API

---

### 项目八：智能体语言优化（多语言，不限于中文）

**目标：** 报错、配置、所有 UI 文本支持用户选择的语言，错误消息附带详解和解决方案。

**当前差距：**
- 所有错误消息硬编码英文
- 无 i18n 基础设施

**方案：**
1. **i18n 模块**：`app/i18n/` 目录，JSON 格式翻译文件
   - `zh_CN.json`, `en_US.json`, `ja_JP.json` 等
   - 覆盖：HTTP 错误、API 描述、配置项、提示词模板、摘要标签
2. **语言检测**：从请求头 `Accept-Language` 或用户配置中获取
3. **错误详解引擎**：`ErrorExplainer` —— 对常见错误码（如 404/500/rate_limit）生成：
   - 翻译后的错误描述
   - 可能的原因（中文/用户语言）
   - 建议解决方案
4. **数据库字段保持英文 key**，只翻译展示层
5. **API 文档多语言**：FastAPI docs 标题/描述支持 i18n

---

### 项目十一：三层工具索引（摘要→标签→完整描述 + 向量搜索 + Token预算）

**目标：** 工具/skill 不靠 Agent 的记忆，而是靠结构化索引。Agent 通过三层检索精准找到需要的工具。

**方案（在 MBclaw-Lite 中实现工具元数据存储和检索）：**
1. **`ToolRegistry` 模型**：
   - `name`, `summary_100`（100字内简介，第一层）
   - `tags`（JSON 数组，第二层，与项目二的分类体系关联）
   - `full_description`（TEXT，第三层完整描述）
   - `embedding`（向量）
   - `compatible_models`（JSON，与项目十二联动）
   - `usage_examples`（JSON）
2. **三层检索 API**：
   - `GET /api/tools/summaries` → 全部工具的100字摘要（轻量）
   - `GET /api/tools/by-tag?tag=xxx` → 按标签筛选（中量）
   - `GET /api/tools/{id}/full` → 单工具完整描述（详细）
   - `POST /api/tools/search` → 向量语义搜索
3. **工具-分类自动关联**：工具添加时，LLM 分析工具描述 → 自动归入项目二的分类树节点
4. **Token 预算 API**：`POST /api/tools/select` — 输入任务描述 + token_budget → 返回预算内最相关的工具列表

---

### 项目十二：多模型能力评分与智能调度

**目标：** 用户添加多个模型的 key 后，系统自动评估每个模型的能力，分配子任务时选择最合适的模型。

**方案（在 MBclaw-Lite 中实现模型元数据 + 推荐引擎）：**
1. **`ModelProfile` 模型**：
   - `key_alias`, `model_name`, `api_base`
   - `capabilities`（JSON：reasoning/coding/vision/search/creativity/speed/cost 各 0-1 分）
   - `strengths`（文字标签）
   - `tool_compatibility`（JSON：与哪些工具配合评分高）
   - `cost_per_1k_tokens`
   - `context_window`
2. **能力自动探测**：
   - 添加 key 后 → 调一次 LLM("你的能力特点是什么？列出你最擅长的5个领域")
   - 结合 Tavily/WebSearch 搜索该模型公开资料
   - 自动填充 capabilities
3. **推荐 API**：`POST /api/models/recommend`
   - 入参：`{task_type, task_complexity, budget, required_tools}`
   - 返回：排序后的模型列表 + 理由
4. **联合优化**：工具选择 + 模型选择同时计算（不是先选工具再选模型）

---

### 项目十三：多编程工具融合（原生接口对接）

**目标：** 对接多种外部工具的原生接口：OpenHands、MiMo Code、图像识别、TTS、STT、智能家居、路由器控制等。

**方案（在 MBclaw-Lite 中实现统一的外部工具注册和调用网关）：**
1. **`ExternalIntegration` 模型**（统一所有外部工具）：
   - `provider`（"openhands"|"mimo"|"image_recognition"|"tts"|"stt"|"smart_home"|"router"|...）
   - `api_key`（加密存储，AES）
   - `base_url`
   - `config`（JSON，各 provider 专属配置）
   - `status`（active/inactive/error）
   - `free_trial_expiry`（如有免费试用）
2. **统一工具网关** `ToolGateway`：
   - 标准化的调用接口：`async def call_tool(provider, action, params) -> result`
   - 每个 provider 有对应的 adapter 实现
3. **Provider Adapter 模式**：
   - `OpenHandsAdapter`：对接 OpenHands Cloud API
   - `MiMoAdapter`：对接 MiMo Code API
   - `ImageRecognitionAdapter`：对接视觉模型 API
   - `TTSAdapter` / `STTAdapter`：对接语音服务
   - `SmartHomeAdapter` / `RouterAdapter`：对接 IoT/网络设备
4. **配置 API**：
   - `POST /api/integrations` → 注册新工具
   - `GET /api/integrations` → 列出所有已注册工具
   - `PATCH /api/integrations/{id}` → 更新配置
   - `DELETE /api/integrations/{id}` → 移除工具
   - `POST /api/integrations/{id}/test` → 测试连通性

---

### 🔵 STAGE B：Agent Runtime 构建（新建 MBclaw-Core）

> 以下项目需要构建 MBclaw 自己的 Agent Runtime。参考 OpenClaw 的事件循环、Agent Loop、Tool 执行机制，用 FastAPI + asyncio 自研实现。

---

### 项目七：用户最新消息优先（新消息=新任务，旧任务不中断转入后台）

**目标：** Agent 跑任务时用户发新消息，默认立即处理新消息，旧任务保存状态后转入后台继续跑。

**MBclaw-Core 实现：**
1. **消息监听器** `MessageListener`：
   - WebSocket 或 SSE 持续监听用户输入
   - 新消息到达 → 比对当前任务 → 判断是否为"新任务"
   - 判断标准：新消息的主题/意图与当前任务不同（用 LLM 语义判断）
2. **任务队列** `TaskQueue`（存在 MBclaw-Lite）：
   - active_task / background_tasks 列表
   - 每个任务有：id, status, progress, checkpoint（可恢复状态）
3. **任务挂起与恢复** `TaskSuspender`：
   - 挂起：保存当前 Agent 状态（对话历史 + 工具执行进度 + 文件状态）→ 标记 background
   - 恢复：从 checkpoint 加载 → 继续执行
   - 旧任务在后台 asyncio task 中继续跑（不阻塞主循环）
4. **Agent Loop 改造**：
   - 每轮迭代开始时先检查消息队列是否有新用户消息
   - 有 → 中断当前（挂起）→ 处理新消息
   - 无 → 继续当前任务

**与 OpenClaw 的关键区别：** OpenClaw 需要 /stop 命令才能中断。MBclaw 默认就是"新消息优先"，不需要特殊命令。

---

### 项目四：全自动模式（自主决策，多方案并行）

**目标：** 用户说"全自动"后，Agent 遇到需要确认的点不再问用户，自己评估选择，用户无回复时自动研究其他选项做出多个成品。

**MBclaw-Core 实现：**
1. **自动模式状态机** `AutoModeStateMachine`：
   - 状态：normal → auto_requested → auto_active → auto_completed
   - 进入 auto_active 后，所有 DecisionPoint 自动处理
2. **决策引擎** `AutoDecisionEngine`：
   - 遇到选择时：列出选项 → LLM 自评每个选项的优劣 → 选最优 → 记录决策日志
   - 决策日志存 MBclaw-Lite（`DecisionLog` 模型）
3. **多方案并行生成器** `ParallelProductGenerator`：
   - 用户长时间无回复 → 自动启动 N 个平行 session
   - 每个 session 走不同方案 → 都存到 MBclaw-Lite
   - 用户回来时展示："我帮你做了3个版本，选一个？"
4. **超时检测**：用户 N 分钟无回复 → 触发并行生成

---

### 项目五：双Key协作（Key1制作 + Key2评审 + 循环改进 1-6轮）

**目标：** 一个模型做产品，另一个模型当评审，找 bug、提改进方案，循环打磨。

**MBclaw-Core 实现：**
1. **协作编排器** `DualKeyOrchestrator`：
   - 输入：task_description, maker_key, reviewer_key, max_cycles
   - 循环流程：
     ```
     for cycle in 1..max_cycles:
         product = maker_key.run(task + review_feedback)  # Key1 制作
         review = reviewer_key.review(product)             # Key2 评审
         if review.score >= threshold: break               # 达标则退出
         task += review.suggestions                        # 未达标则继续改
     ```
2. **评审模型** `ReviewResult`（存 MBclaw-Lite）：
   - score（0-100）, suggestions, bugs_found, improvements
   - 每轮评审都存档
3. **收敛检测**：连续2轮 score 无显著提升 → 自动终止

---

### 项目九：启动/安全/配置检查（兼容性保障，不删除而是确保可用）

**目标（已修改）：** 不是删除检查，而是确保所有检查与 MBclaw 配置兼容。冲突时优先保证 MBclaw 启动，然后告知用户冲突项和修复方案。

**MBclaw-Core 实现：**
1. **启动检查器** `StartupChecker`：
   - 步骤1：检查所有依赖（Python版本、包、数据库连接）
   - 步骤2：检查 LLM API Key 连通性（逐个 ping）
   - 步骤3：检查外部集成（OpenHands、MiMo 等）连通性
   - 步骤4：检查文件系统权限（data/、memory/、snapshots/ 可写）
   - 步骤5：检查配置完整性（必填项是否填写）
2. **冲突处理策略**：
   - 非致命冲突 → 记录 warning log → 继续启动
   - 致命冲突 → 优先绕过，保证 MBclaw 核心启动 → 启动后通知用户
3. **自修复引擎** `SelfHealer`：
   - 可自动修复的：创建缺失目录、设置默认值
   - 需用户确认的：生成修复方案 → 通知用户选择
4. **健康检查 API**：`GET /api/health` → 返回所有组件状态

---

### 项目十：多子对话协同（自主反思 + 共享通道 + 去重复用 + 冲突协商）

**目标：** 子 Agent 完成任务后自主反思并发布到共享通道，其他 Agent 启动前先查是否有已有结果可直接复用，遇到矛盾自动协商。

**MBclaw-Core 实现：**
1. **共享通道** `SharedChannel`（存 MBclaw-Lite）：
   - 每个 project 一个 channel
   - 子 Agent 发布消息：`{agent_id, type: "reflection"|"result"|"warning", content, task_hash}`
2. **任务指纹去重** `TaskDeduplicator`：
   - 新任务 → SHA256(task_description) → 查 SharedChannel
   - 已存在 → 直接复用结果，不再重复执行
3. **自主反思协议** `ReflectionProtocol`：
   - 子 Agent 完成后自动生成反思摘要（做了什么、发现什么、踩了什么坑、建议）
   - 发布到 SharedChannel
4. **冲突检测与协商** `ConflictResolver`：
   - 两个 Agent 对同一文件/资源有矛盾操作 → 写入 ConflictLog
   - 启动协商 Agent（第三个 Agent）分析双方理由 → 给出合并方案
5. **整个过程完全自主**，不需要主 Agent 编排

---

### 🔵 STAGE C：最终构想 — MBclaw 满血状态

---

### 最终构想：主动化智能（感知 → 分析 → 介入）

**目标：** MBclaw 不再是"等用户发消息"的被动助手，而是主动监测用户行为、预判需求、自主提供帮助的智能体。

#### 核心能力：

**1. 用户行为感知层** `UserBehaviorMonitor`：
- 客户端（Win/Mac/Linux/Android）安装轻量 Agent，监测：
  - 用户当前操作的应用和动作（如：重复点击删除、搜索关键词、打开的文件）
  - 操作频率和模式（如：1分钟内重复同一操作超过5次）
- 数据上报到 MBclaw-Lite（`UserBehaviorLog` 模型）

**2. 意图分析引擎** `IntentAnalyzer`：
- 实时分析用户行为流 → 判断用户意图
- 例子1：检测到"QQ 重复点击删除好友" → 意图："用户想批量删除，但操作繁琐"
- 例子2：检测到"搜索小米刷 Win10" → 意图："用户想刷机但不知如何操作"

**3. 主动介入决策** `ProactiveIntervention`：
- 匹配意图 → 能力库，判断 MBclaw 能否帮助
- 能 → 推送通知（通知栏/弹窗），提供选项：
  - "MBclaw 检测到您在重复删除QQ好友，需要我帮您吗？"
  - 选项1：模拟屏幕操作（辅助点击）
  - 选项2：后台克隆环境自动执行
  - 选项3：帮我选中，我来点删除
  - 选项4：不需要
- 用户选择后 → 自动执行

**4. 后台自动化执行（以刷机为例）**：
- 用户同意后：
  - 自动搜索整理教程 → 生成保姆级步骤
  - 手机端：自动开启 USB 调试
  - PC端：自动下载镜像、驱动
  - 执行刷机 → 监控进度 → 失败自动查原因 → 重试
  - 10 次后仍失败 → 恢复原镜像 + 恢复用户数据（照片、聊天记录、常用软件）
  - 全程只需用户第一次同意 + 插上 USB 线

**5. Embedding 模型智能推荐**：
- 检测用户 IP（中国 IP → 推荐阿里云 text-embedding-v3 或智谱 embedding-3；外国 IP → 推荐 OpenAI embeddings）
- 说明这些模型兼容 OpenAI 接口
- 用户跳过 → 降级为纯 FTS（全文搜索）
- 之后主动询问是否配置

#### 最终构想的技术依赖：

| 能力 | 技术需求 | 当前状态 |
|------|---------|---------|
| 行为监测 | 客户端 Agent（Win/Mac/Android） | ❌ 需新建 |
| 屏幕模拟操作 | ADB（Android）/ Accessibility API（Win） | ❌ 需新建 |
| 环境克隆 | Android 模拟器 / Docker 容器 | ❌ 需新建 |
| 设备固件操作 | fastboot / adb / platform-tools | ❌ 需新建 |
| 推送通知 | WebSocket + 系统通知 API | ❌ 需新建 |

> **最终构想属于远期目标**，需要在 Stage A 和 Stage B 全部完成后才有基础实现。

---

## 5. TESTING AND VALIDATION

### Stage A（MBclaw-Lite）测试：
- 项目一：pytest 验证 transcript 包含 thinking + changed_files
- 项目二：pytest 验证分类树 CRUD、LLM 分类结果存储、向量搜索命中
- 项目三：pytest 验证快照创建/恢复
- 项目六：pytest 验证 context-search API 三层检索
- 项目八：pytest 验证多语言错误消息
- 项目十一：pytest 验证三层工具检索、向量搜索
- 项目十二：pytest 验证模型推荐 API
- 项目十三：pytest 验证集成配置 CRUD + 连通性测试

### Stage B（MBclaw-Core）测试：
- 项目七：模拟用户打断 → 验证旧任务挂起 + 新任务处理 + 旧任务恢复
- 项目四：模拟决策点 → 验证自动选择 + 决策日志
- 项目五：双 Key 协作循环 → 验证 1-6 轮迭代 + 评审记录
- 项目九：模拟各种故障 → 验证启动检查 + 自修复
- 项目十：多子 Agent 并发 → 验证共享通道 + 去重 + 冲突协商

### Stage C（MBclaw-Full）测试：
- 端到端：模拟用户重复操作 → 验证主动介入推送
- 端到端：模拟刷机场景 → 验证全自动流程

---

## 6. 实施优先级

### P0 — 存储层核心（MBclaw-Lite，可立即开始）：
1. **项目二**：树形分类 + 失败方案（核心差异化）
2. **项目一**：增强 transcript
3. **项目八**：多语言优化
4. **项目六**：实时记忆检索

### P1 — 存储层高级 + 工具/模型基础设施：
5. **项目十一**：三层工具索引
6. **项目十二**：模型能力注册
7. **项目十三**：多工具融合网关
8. **项目三**：突破快照

### P1+ — Hermes 记忆系统增强（借鉴 NousResearch/Hermes-Agent 的 6 个核心模式）：

> 以下 6 个项目是对 MBclaw 记忆系统的架构升级，灵感来自 Hermes-Agent 的自我进化闭环设计。在当前 P0+P1 的存储基础上，引入冻结快照、自动技能提取、Curator 生命周期管理、写入审批门等机制。

#### H1 — 冻结内存快照 + 字符预算 + 批量操作（借鉴模式 1+2）

15. **项目 H1a — MemoryStore 双态架构**：`_system_prompt_snapshot`（冻结，会话开始时加载）+ `_live_entries`（实时，写入即落盘）。`format_for_system_prompt()` 永远返回冻结快照，保证同一 session 内系统提示词字节不变，最大化 LLM KV 前缀缓存命中率。
16. **项目 H1b — 硬性字符预算**：MEMORY.md 上限 2200 chars，USER.md 上限 1375 chars。超限时不自动截断，而是返回当前全部条目 + 错误提示让 LLM 自行判断合并/删除。
17. **项目 H1c — 批量原子操作 API**：`POST /api/memory/batch`，入参 `{operations: [{action: "remove"|"replace"|"add", ...}]}`，所有操作在一个事务中原子执行，只对最终结果做预算检查（中间态溢出无关）。

#### H2 — 陈述性记忆 vs 程序性记忆分离（借鉴模式 6）

18. **项目 H2a — 新建 SkillCard 模型**：`name`, `trigger_condition`, `steps`（JSON 步骤列表）, `known_pitfalls`（已知坑）, `category`, `created_by`（"agent"|"user"）, `pinned`（bool）, `last_used_at`, `usage_count`, `status`（active/stale/archived）, `created_at`。
19. **项目 H2b — 重定义存储语义**：
    - 陈述性（Facts）：MEMORY.md（环境约定）、USER.md（用户偏好）、ProjectDNA（项目事实）、Summary（对话摘要）
    - 程序性（Procedures）：SkillCard（可复用过程）、ClassificationNode.successful_approaches、ClassificationNode.failed_approaches
20. **API**：`POST/GET/PATCH/DELETE /api/skills`，`POST /api/skills/search`（向量语义搜索技能卡）

#### H3 — 自动技能提取（借鉴模式 3）

21. **项目 H3a — 技能提取触发器**：Agent Loop 每轮任务结束后统计：
    - 工具调用次数 ≥ 5 → 触发
    - 错误修正次数 ≥ 2 → 触发
    - 用户纠正后成功的方案 → 触发
    - 用户明确说"记住这个做法" → 强制触发
22. **项目 H3b — SkillExtractor 服务**：输入完整对话历史 → LLM 分析 → 自动生成 SkillCard（含触发条件、步骤、已知坑），`created_by="agent"`。
23. **项目 H3c — 去重检查**：提取前对新技能的 `trigger_condition` 做 SHA256 → 查现有 SkillCard 是否已存在相同流程 → 已存在则更新而不新增。

#### H4 — Curator 自动化生命周期管理（借鉴模式 4）

24. **项目 H4a — 时间戳驱动自动迁移**（纯 SQL，不调 LLM，零 API 成本）：
    - 30 天未使用 → 标记 stale
    - 90 天未使用 → 归档 archived
25. **项目 H4b — 三条防线防误删**：
    - ① `pinned=true` 的技能卡永久跳过
    - ② 新建技能卡首次遇到跳过（seed-on-first-sight，防止刚装系统时所有技能被瞬间归档）
    - ③ 只触碰 `created_by="agent"` 的技能卡，`created_by="user"` 的从不自动归档
26. **项目 H4c — Curator 调度**：IdleTaskScheduler 扩展，每 24 小时或 Agent 空闲 ≥ 2 小时时运行一次。

#### H5 — 写入审批门（借鉴模式 5，MBclaw 独创细化）

> 这是 MBclaw 对 Hermes 写入审批门的增强版——支持用户自定义审批阈值，按操作风险自动分级。

27. **项目 H5a — WriteApprovalGate 核心模型**：
    ```python
    # 审批阈值定义（用户可配）
    class ApprovalThreshold:
        MINIMAL   = 0.05   # 极低：几乎不审，只审最危险的
        LOW       = 0.25   # 低
        MEDIUM    = 0.45   # 中（默认推荐）
        HIGH      = 0.70   # 中高
        MAXIMUM   = 0.95   # 极高：几乎所有写入都要审
        FULL_AUTO = 1.00   # 全自动：永不审批
    ```

28. **项目 H5b — 操作风险评分引擎** `RiskScorer`：
    每一项写入操作自动计算风险分数（0~1），维度如下：

    | 风险维度 | 权重 | 评分规则 |
    |---------|------|---------|
    | `subsystem` | 0.30 | memory=0.3, skill=0.6, dna=0.7, snapshot_delete=0.9 |
    | `scope` | 0.25 | 单条新增=0.1, 修改已有=0.4, 批量删除=0.8, 全量清空=0.95 |
    | `origin` | 0.20 | 用户手动=0.0, Agent 前台=0.3, Agent 后台=0.6, 守护进程=0.8 |
    | `content_size` | 0.10 | <100chars=0.1, 100~500=0.2, 500~2000=0.4, >2000=0.7 |
    | `modifies_existing` | 0.15 | 纯新增=0.1, 修改已有=0.5, 删除已有=0.8 |

    **风险分数** = Σ(维度权重 × 维度评分)  →  归一化到 0~1

29. **项目 H5c — 审批决策矩阵**：
    ```
    风险分数 ≤ 用户阈值  →  AUTO_APPROVE（自动批准，写入 + 记录日志）
    风险分数 > 用户阈值  →  REQUIRE_APPROVAL（暂停，通知用户审批）
    ```

30. **项目 H5d — 自动批准的写入也要展示**：
    低于阈值的操作自动执行，但写入 `ApprovalLog` 表（`operation`, `risk_score`, `decision="auto_approved"`, `timestamp`），提供 `GET /api/approvals/log` 端点供用户事后审查。

31. **项目 H5e — 需要审批的操作**：
    写入 `PendingApproval` 表，包含完整 payload（可重放），状态 `pending/approved/rejected`。用户通过 `POST /api/approvals/{id}/approve` 或 `/reject` 处理。批准后重放原始 payload 完成写入。

32. **项目 H5f — 阈值 API**：
    - `GET /api/settings/approval-threshold` → 返回当前阈值（默认 MEDIUM=0.45）
    - `PATCH /api/settings/approval-threshold` → 用户修改：`{level: "low"}` 或 `{custom: 0.30}`
    - 保存到 `UserSettings` 表，按 user 粒度生效

33. **项目 H5g — 各阈值含义速查**：

    | 阈值 | 值 | 含义 | 自动批准示例 | 需审批示例 |
    |------|-----|------|------------|-----------|
    | 极低 | 0.05 | 几乎不审 | 用户手动新增单条 memory | Agent 后台批量删除 skill 卡 |
    | 低 | 0.25 | 宽松 | Agent 前台新增 memory、用户改 skill | Agent 后台修改 DNA、批量操作 |
    | **中** | **0.45** | **推荐默认** | Agent 前台新增 skill、修改单条 memory | Agent 后台删除记忆、全量操作 |
    | 中高 | 0.70 | 严格 | 大部分前台操作 | Agent 大部分后台写入 |
    | 极高 | 0.95 | 极严 | 仅用户手动操作 | Agent 所有自动写入 |
    | 全自动 | 1.00 | 永不审批 | 一切操作 | （无） |

34. **项目 H5h — 通知机制**：有待审批操作时，通过 WebSocket 或 SSE 推送通知给客户端（"有 3 个 Agent 操作需要您审批"）。

#### H6 — 外部漂移检测（借鉴模式 1 的防御机制）

35. **项目 H6 — DriftDetector**：每次 MemoryStore 写入前，对比磁盘文件的 SHA256 和上次读取时的 SHA256。不一致 → 创建 `.bak.{timestamp}` 备份 → 拒绝本次突变 → 返回"外部工具修改了文件，已备份，请检查后重试"。防止 patch 工具、shell 追加、多进程并发导致静默数据丢失。

---

### P2 — Agent Runtime 构建（MBclaw-Core，新建）：
36. **项目九**：启动检查 + 自修复（先做，保证后续开发顺利）
37. **项目七**：消息优先级 + 后台任务
38. **项目四**：全自动模式
39. **项目十**：子对话协同
40. **项目五**：双Key协作

### P3 — 远期：
41. **最终构想**：主动智能（需要客户端 + 设备控制能力）
