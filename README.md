# MBclaw-Lite

AI 长期记忆智能体系统 — FastAPI + SQLite + ChromaDB。拥有多渠道消息网关、Agent Runtime、Hermes 风格记忆体系。

## 项目状态

| 指标 | 数值 |
|------|------|
| 总项目数 | 33/34 ✅（仅 MiMo 未做） |
| Python 文件 | 123 |
| 代码行数 | 11,721 |
| 测试 | 137（全量通过） |
| API 路由 | 26 |
| 数据模型 | 24 |
| 业务服务 | 39 |

[完整实现状态 →](docs/11-implementation-status.md) | [设计文档 →](https://github.com/mengbaiyoudianxian/MBclaw)

## 核心功能

### 记忆系统（Hermes H1-H6）
- **MEMORY.md + Daily Notes**：双态架构（snapshot + live），LLM KV 前缀缓存稳定
- **Dreaming**：短期→长期自动整合，Memory Flush 上下文保存
- **Skill Auto-Extraction**：对话→触发→提取→去重→SkillCard
- **Curator**：纯 SQL 生命周期（30天 stale / 90天 archived），零 LLM 成本
- **Write-Approval Gate**：风险评分 + 用户可设阈值 + 自动/待审批

### Agent Runtime
- **Execution Loop**：LLM → tools → memory → H3 extraction
- **Context Builder**：记忆 L1/L2/L3 + 活跃技能 + ProjectDNA
- **Self-Correction**：错误反馈，max_errors=3
- **Sub-Agent Coordinator**：去重检查 + 冲突协商 + 共享通道

### 消息网关（11 平台）
Telegram · 飞书 · 企业微信 · QQ · 微信公众号 · WhatsApp · Signal · LINE · Discord · Slack · 钉钉

### 其他
- **Thought Collision**：组合创新引擎
- **乌托邦计划**：QQ/微信/飞书/企业微信聊天提取+分析
- **用户画像**：Feedback + Psychology Profile
- **多模型调度**：能力评分 + 成本感知 + 联合优化
- **i18n**：全中文错误消息 + 多语言中间件
- **生产部署**：Docker + K8s + StartupChecker

## 项目结构

```
MBclaw-Lite/
├── app/
│   ├── main.py              # FastAPI 入口（26 routers）
│   ├── config.py            # 配置
│   ├── database.py          # SQLite + ChromaDB
│   ├── models/              # 24 数据模型
│   ├── routers/             # 26 API 路由（含 gateway）
│   ├── schemas/             # 19 Pydantic schema
│   ├── services/            # 39 业务服务
│   │   └── gateway/         # 11 平台适配器
│   ├── middleware/          # Locale 中间件
│   └── i18n/               # 多语言资源
├── tests/                   # 137 tests
├── k8s/                     # Kubernetes manifests
├── data/                    # 运行时数据
├── Dockerfile               # 生产镜像
└── docs/                    # 文档
```

## 快速开始

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## License

MIT