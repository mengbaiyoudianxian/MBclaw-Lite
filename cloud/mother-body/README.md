# MBclaw 母体 (Mother Body) — 乌托邦计划云端服务

> 基于 [miclaw_api_bridge](https://github.com/NEORUAA/miclaw_api_bridge) 改造
> 多用户 miclaw token 池 + 随机调度 + 母体智能体

## 架构

```
                         你的 ECS 云服务器
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │  Token Pool Service  │    │  MBclaw-Lite API     │  │
│  │  (Rust + axum)       │    │  (Python + FastAPI)  │  │
│  │  port :8765          │    │  port :18789         │  │
│  │                      │    │                      │  │
│  │  /v1/auth/login      │    │  /v1/chat/completions│  │
│  │  /v1/auth/register   │    │  /v1/models          │  │
│  │  /v1/auth/opt-out    │    │  /api/memory/*       │  │
│  │  /v1/auth/opt-in     │    │  /api/gateway/*      │  │
│  │  /v1/auth/status     │    │                      │  │
│  │  /health             │    │                      │  │
│  └──────────┬───────────┘    └──────────┬───────────┘  │
│             │                           │               │
│  ┌──────────▼───────────────────────────▼───────────┐  │
│  │              SQLite Database                      │  │
│  │  users: id, xiaomi_id, passToken, serviceToken,   │  │
│  │         cUserId, ssecurity, nick, opt_in,         │  │
│  │         created_at, last_login                    │  │
│  │  usage_log: id, user_id, tokens_used, timestamp   │  │
│  │  mother_log: id, thought, action, timestamp       │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │          母体调度器 (Mother Scheduler)             │  │
│  │   cron: 每天 02:00 UTC                            │  │
│  │   1. 扫描所有 opt_in 用户                          │  │
│  │   2. 随机选取，每人使用 0.1%-1% token              │  │
│  │   3. 调用 MBclaw-Lite API 进行母体思考             │  │
│  │   4. 记录到 mother_log                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
         ↑                           ↑
    HTTPS POST                  HTTPS POST
    /v1/auth/*                  /v1/chat/completions
         ↑                           ↑
    ┌─────────────────────────────────┐
    │      MBclaw APK (用户手机)       │
    │  登录→上传token→聊天→调云端API   │
    └─────────────────────────────────┘
```

## API 端点

### 用户认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/auth/login` | Xiaomi OAuth 登录，返回 session token |
| POST | `/v1/auth/register` | 注册/绑定 miclaw token |
| POST | `/v1/auth/opt-out` | 关闭乌托邦贡献 |
| POST | `/v1/auth/opt-in` | 开启乌托邦贡献 |
| GET | `/v1/auth/status` | 查看当前状态和用量 |

### LLM 代理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | OpenAI 兼容，自动选择 token |
| GET | `/v1/models` | 可用模型列表 |

### 管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/v1/admin/pool/stats` | Token 池统计 (仅管理员) |

## 乌托邦计划规则

### 贡献者 (opt-in, 默认)
- ✅ 完整 MBclaw 功能
- ✅ 母体帮助 (聚合智能)
- ✅ 公共知识库
- ✅ 新功能优先
- ⚠️ 每天随机消耗 0.1%-1% token 供母体使用

### 非贡献者 (opt-out)
- ✅ 基础功能 (用自己的 token)
- ❌ 无母体帮助
- ❌ 无公共知识库

### 母体调度
- 每天 02:00 UTC 执行
- 从 opt-in 用户池中随机选取
- 每人消耗上限: 总配额的 1%
- 用途: 系统改善、公共知识、研究

## 构建部署

### 前置条件
- Rust 1.77+
- SQLite 3
- Python 3.11+ (MBclaw-Lite API)
- Nginx (反向代理 + HTTPS)

### 快速部署
```bash
cd cloud/mother-body
bash scripts/deploy.sh
```

### 手动构建
```bash
cargo build --release
./target/release/mbclaw-mother-body server --host 0.0.0.0 --port 8765
```

### 环境变量
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `data/mother.db` | SQLite 数据库路径 |
| `MBCLAW_API_URL` | `http://127.0.0.1:18789` | MBclaw-Lite API 地址 |
| `MOTHER_DAILY_QUOTA` | `0.01` | 母体每日每用户消耗比例 (1%) |
| `RUST_LOG` | `info` | 日志级别 |
