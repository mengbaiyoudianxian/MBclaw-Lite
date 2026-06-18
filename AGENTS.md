# MBclaw-Lite 项目记忆

## 架构概述
MBclaw-Lite = FastAPI + SQLite + ChromaDB 存储层。三个阶段的路线图：
- **MBclaw-Lite**（存储层，✅ Stage A 完成 8/8 项目，39 tests）
- **MBclaw-Core**（Agent Runtime，待建）
- **MBclaw-Full**（主动智能，远期）

## 记忆系统设计（借鉴 Hermes-Agent 6 模式）

### 陈述性 vs 程序性 分离
- **陈述性（Facts）**: MEMORY.md, USER.md, ProjectDNA, Summary, Keyword, ClassificationNode 分类结构
- **程序性（Procedures）**: SkillCard（新模型）, ClassificationNode.successful_approaches, ClassificationNode.failed_approaches

### MemoryStore 双态架构
- `_system_prompt_snapshot`: 会话开始时 `load_from_disk()` 冻结，`format_for_system_prompt()` 永远返回此快照
- `_live_entries`: 实时状态，写入即落盘，但绝不触及快照
- 目的: LLM KV 前缀缓存稳定性

### 字符预算
- MEMORY.md 上限 2200 chars
- USER.md 上限 1375 chars
- 超限时返回全部条目 + 错误提示 → LLM 自行压缩（非自动截断）

### 批量原子操作
- `POST /api/memory/batch`: `{operations: [{action: "remove"|"replace"|"add", ...}]}`
- 所有操作原子执行，只对最终结果做预算检查

### SkillCard 自动提取触发器
- 工具调用 ≥ 5 次
- 错误修正 ≥ 2 次
- 用户纠正后成功
- 用户明确说"记住这个做法"
- 提取时 SHA256 去重检查

### Curator 生命周期（纯 SQL，零 LLM 成本）
- 30 天未用 → stale, 90 天未用 → archived
- 防线: ①pinned 跳过 ②新技能首次跳过 ③只碰 agent-created

### 写入审批门（MBclaw 独创细化）
- 用户可设阈值: 极低=0.05, 低=0.25, 中=0.45(默认), 中高=0.70, 极高=0.95, 全自动=1.00
- 风险分数 = Σ(维度权重 × 维度评分)
- 维度: subsystem(0.30), scope(0.25), origin(0.20), content_size(0.10), modifies_existing(0.15)
- 低于阈值 = AUTO_APPROVE（写入 + ApprovalLog 记录）
- 高于阈值 = PendingApproval（等待用户审批）
- 自动批准的也要展示（GET /api/approvals/log）

### 外部漂移检测
- 写入前 SHA256 对比磁盘 vs 上次读取，不一致则备份 + 拒绝
