# MBclaw Android APK — 完整架构设计

> 基于 miclaw APK (HyperOS 魔改版)，保留 ~70% UI，更换 AI 内核为 MBclaw
> 本地 Linux 沙箱 + 云端服务器链路 + 语音全接管

## 一、总体架构

```
┌──────────────────────────────────────────────────────────┐
│                   MBclaw Android APK                      │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Miclaw UI  │  │  MBclaw      │  │  Voice System  │  │
│  │  (~70%保留) │  │  Agent Chat  │  │  (AIVSE劫持)   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│  ┌──────▼────────────────▼───────────────────▼────────┐  │
│  │              MBclaw Agent Runtime                   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │  │
│  │  │ Python   │ │ Node.js  │ │ LLM Client         │  │  │
│  │  │ Runtime  │ │ Runtime  │ │ (OpenAI compat)    │  │  │
│  │  └──────────┘ └──────────┘ └────────────────────┘  │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │              Miclaw Bridge (MCP Protocol)           │  │
│  │    386+ tools via MCP: WiFi/蓝牙/短信/相机/...       │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │           Local Linux Sandbox (proot)               │  │
│  │    Ubuntu rootfs: Python/Node.js/Git/编译器/...      │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │          Cloud Connector (WebSocket Tunnel)          │  │
│  │     本地 ↔ ECS 双向隧道 (frp/Cloudflare Tunnel)      │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 二、模块说明

### 2.1 Miclaw Bridge — 工具桥接层

```
MBclaw Agent → MCP Client → Miclaw MCP Server → Android APIs
              (stdio/sse)    (内置386+工具)

工具分类：
  ✅ 系统设备 (42) — WiFi、蓝牙、设置、剪贴板
  ✅ 通讯 (30)   — 短信、电话、联系人
  ✅ 文件 (13)   — 读写、搜索、操作
  ✅ 媒体 (42)   — 相机、录屏、录音、图库
  ✅ 应用 (11)   — 管理、商店
  ✅ 日历 (17)   — 日程 CRUD
  ✅ 笔记 (27)   — 笔记管理
  ✅ 浏览器 (9)  — 自动化
  ✅ 语音 (7)    — TTS
  ✅ 设备互联 (9) — 跨设备协作
  ✅ 管理 (12)   — 提醒、闹钟、定时器
  ✅ 搜索 (3)    — 网页搜索
  ✅ 生活 (63)   — 地图、出行、购物、音乐
  ✅ 图片 (26)   — 图片处理
  ✅ 账号 (21)   — 账号管理
  ✅ Agent (13)  — Agent管理
  ✅ 云服务 (8)  — 云服务
  ✅ 开发者 (22) — 终端、测试
```

### 2.2 Local Linux Sandbox — 本地沙箱

```
proot + Ubuntu rootfs → 完整 Linux 环境
用途：
  - 执行危险命令（rm -rf 隔离）
  - 运行 Python/Node.js 代码
  - pip/npm 安装包
  - 编译 C/C++/Rust 项目
  - 文件转换 (ffmpeg/pandoc)
  - 数据分析 (pandas/numpy)

安全边界：
  - proot 隔离文件系统
  - seccomp 系统调用过滤
  - 内存/cpu 限制 (cgroups)
  - 网络可配置白名单
```

### 2.3 Cloud Connector — 云端链路

```
手机端 ←→ WebSocket Tunnel ←→ ECS 云端

方案：
  主: Cloudflare Tunnel (cloudflared)
      - 免费、无需公网IP
      - 自动 HTTPS
      - DDoS 防护

  备: frp (内网穿透)
      - 自建服务器
      - TCP/UDP/HTTP 全协议

使用场景：
  - 手机算力不够 → 云端 GPU 推理
  - 手机存储不够 → 云端 ChromaDB 向量库
  - 多设备协同 → 云端统一记忆

无需 VPN：WebSocket 加密隧道，手机端自动连接
```

### 2.4 Voice System — 语音全接管

```
AIVSE SDK → MBclaw WakeWord → MBclaw Speech Pipeline

流程：
  1. 用户说唤醒词（可自定义，默认"小爱同学"）
  2. AIVSE SDK 检测到唤醒词
  3. MBclaw 拦截唤醒事件（不发往小米服务）
  4. 开启连续录音
  5. VAD (Voice Activity Detection) 实时检测
  6. 5-6 秒静音 → 自动断句 → 发送到 MBclaw Agent
  7. Agent 处理 → TTS 语音回复
  8. 继续监听下一句（连续对话模式）

特性：
  - 唤醒词可自定义（替换"小爱同学"）
  - 连续对话（无需重复唤醒）
  - 自动断句（VAD 静音检测）
  - 流式 TTS（边说边生成）
  - 离线唤醒（AIVSE 本地模型）
```

### 2.5 MBclaw Agent Runtime

```
Android 上运行 Python 3.11+ 的途径：

  方案A: Chaquopy (推荐)
    - Gradle 插件，APK 内嵌 Python
    - pip 包管理
    - JNI 桥接

  方案B: Termux + proot
    - 完整 Linux 环境
    - 所有 pip/npm 包可用
    - 独立进程，IPC 通信

  方案C: PyTorch Mobile + ONNX
    - 轻量推理
    - 不需要完整 Python

推荐：A + B 组合
  - Chaquopy 跑 MBclaw-Lite API 服务
  - proot 跑沙箱危险操作
```

## 三、UI 定制方案 — 保留 70%

```
miclaw 原始 UI → MBclaw 改装

保留 (70%):
  ✅ 对话气泡布局
  ✅ 输入框 + 发送按钮
  ✅ Agent 选择器（改为 MBclaw Agent 列表）
  ✅ 工具抽屉（工具分类列表）
  ✅ 设置页面布局
  ✅ 语音按钮
  ✅ 暗色/亮色主题

替换 (30%):
  🔄 顶部标题栏 → MBclaw Logo + "MBclaw"
  🔄 启动屏 → MBclaw 动画
  🔄 图标 → MBclaw 图标（蓝紫色调）
  🔄 配色 → 蓝紫主色 + 白/黑辅色
  🔄 Agent 列表 → MBclaw 子 Agent
  🔄 设置项 → MBclaw 配置（LLM/记忆/网关）
  🔄 关于页面 → MBclaw 版本信息

新增:
  ➕ 网关状态面板（11 平台连接状态）
  ➕ 记忆面板（MEMORY.md 查看/编辑）
  ➕ 技能面板（SkillCard 列表）
  ➕ 沙箱终端（本地 Linux 终端）
  ➕ 云端状态指示器
```

## 四、数据流

### 文字对话
```
用户输入 → MBclaw Agent Runtime
              ↓
         Miclaw Bridge (工具调用)
              ↓
         MBclaw API (LLM推理)
              ↓
         本地沙箱 (代码执行)
              ↓
         TTS 回复 (语音输出)
              ↓
         对话气泡 (UI显示)
```

### 语音对话
```
语音唤醒 → VAD 录音 → STT 转文字 → MBclaw Agent → TTS 回复
                                              ↓
                                        Miclaw Bridge
                                        (如需要工具)
```

### 云端转发
```
手机 LLM 请求 → Cloud Connector → ECS MBclaw-Lite API
                                         ↓
                                   ChromaDB / LLM / Agent
                                         ↓
                                   WebSocket 返回结果
```

## 五、构建系统

```
android/
├── build.gradle.kts          # 根构建配置
├── settings.gradle.kts       # 模块配置
├── gradle.properties         # 签名/密钥
├── app/                      # 主 APK 模块
│   ├── build.gradle.kts      # 依赖: Chaquopy, OkHttp, WebSocket
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/mbclaw/  # 所有 Java/Kotlin 代码
│       └── res/              # 资源文件
├── mbclaw-core/              # C++ native 模块 (JNI)
│   └── src/main/cpp/
├── scripts/                  # 构建/部署脚本
│   ├── build.sh              # 完整构建
│   ├── install.sh            # ADB 安装
│   ├── setup_sandbox.sh      # 初始化本地沙箱
│   └── setup_cloud.sh        # 初始化云端链路
└── docs/
    ├── ARCHITECTURE.md       # 本文件
    ├── BUILD.md              # 构建指南
    └── DEPLOY.md             # 部署指南
```

## 六、miclaw API Key 集成

如果用户有 miclaw 内测权限：

```kotlin
// MiclawApiConfig.kt
object MiclawApiConfig {
    // 优先级: 内测Key > 自建Key > 免费模式
    fun resolveApiKey(): String {
        // 1. 用户输入的内测 Key
        userProvidedKey?.let { return it }
        // 2. 绑定的 miclaw 账号 Token
        miclawAccountToken?.let { return it }
        // 3. 免费模式（本地 LLM / DeepSeek 免费 API）
        return "free-mode"
    }

    fun getEndpoint(): String {
        return when (resolveMode()) {
            Mode.BETA -> "https://api.mify.mioffice.cn/v1"
            Mode.SELF -> "https://${userServer}/v1"
            Mode.FREE -> "http://127.0.0.1:${localPort}/v1"
        }
    }
}
```

## 七、安全设计

| 层级 | 措施 |
|------|------|
| 沙箱隔离 | proot + seccomp + cgroups |
| 网络隔离 | 沙箱网络白名单 |
| 文件隔离 | 沙箱 `/data/mbclaw/sandbox/` 只读挂载外部 |
| 权限控制 | Android 权限按需申请 |
| API 密钥 | Android Keystore 加密存储 |
| 通信加密 | WebSocket TLS + 证书锁定 |
| 语音数据 | 本地处理，不上传云端（可选） |

## 八、开发路线图

| 阶段 | 内容 | 预估 |
|------|------|------|
| P0 | 基础框架：构建系统 + Miclaw Bridge + Agent Runtime | 1周 |
| P1 | 本地沙箱：proot Ubuntu + pip/npm 环境 | 3天 |
| P2 | 语音系统：AIVSE 劫持 + VAD + STT + TTS | 1周 |
| P3 | 云端链路：Cloudflare Tunnel + 自动连接 | 2天 |
| P4 | UI 改装：MBclaw 品牌 + 新面板 | 3天 |
| P5 | 集成测试 + 签名打包 | 2天 |
