# MBclaw APK 修改明细

> 基于 miclaw 魔改版带sese (com.aios.osbot, v0.3.3017.BEI)
> 策略: 保留包名、替换品牌、改 API 端点、改语音路由、加登录流程

## 源文件

```
miclaw-apks/魔改版带sese.apk  (69MB)
  → apktool d → miclaw-decompiled/sese-decompiled/
```

## 修改清单 (16 文件 + 8 图标)

---

### P0-1: API 端点替换 (4 文件)

| # | 文件 | 行 | 改前 | 改后 |
|---|------|----|------|------|
| 1 | `smali_classes3/kn/g.smali` | 2060 | `https://api.mify.mioffice.cn/v1/chat/completions` | `https://<CLOUD_HOST>/v1/chat/completions` |
| 2 | `smali/com/aios/osbot/data/repository/c2.smali` | 198 | `https://api.miclaw.xiaomi.net/llm-proxy/mify/v1` | `https://<CLOUD_HOST>/v1` |
| 3 | `smali/v9/x.smali` | 23 | `https://api.miclaw.xiaomi.net/llm-proxy/mify/v1` | `https://<CLOUD_HOST>/v1` |
| 4 | `smali/v9/f0.smali` | 69 | `https://api.miclaw.xiaomi.net/llm-proxy/mify/v1` | `https://<CLOUD_HOST>/v1` |

**smali 约束**: `const-string` 新字符串长度 ≤ 原长度。
- 原 URL: 48 chars (`https://api.mify.mioffice.cn/v1/chat/completions`)
- 新 URL 需 ≤ 48 chars，建议用短域名。如有必要用 `const-string/jumbo`。

**`res/xml/network_security_config.xml`**:
```xml
<!-- 改前 -->
<domain includeSubdomains="true">model.mify.ai.srv</domain>

<!-- 改后: 添加云服务器 -->
<domain includeSubdomains="true"><CLOUD_HOST></domain>
<!-- 保留原有的 127.0.0.1 和 localhost -->
```

---

### P0-2: 语音路由 (4 文件)

| # | 文件 | 行 | 改前 | 改后 |
|---|------|----|------|------|
| 1 | `assets/trigger_router_config.json` | 全部 | `{"package":"com.xiaomi.type","triggerAction":"com.mi.ime.AI_INTERACTION","triggerActivity":"com.mi.ime.ai.AiInteractionActivity"}` | `{"package":"com.aios.osbot","triggerAction":"android.intent.action.MAIN","triggerActivity":"com.aios.osbot.MainActivity"}` |
| 2 | `smali/com/aios/osbot/xaf/q.smali` | 321 | `const-string v5, "com.miui.voiceassist"` | `const-string v5, "com.aios.osbot"` |
| 3 | `smali/vb/o.smali` | 194 | `const-string v5, "com.xiaomi.type"` | `const-string v5, "com.aios.osbot"` |
| 4 | `AndroidManifest.xml` | queries | `<package android:name="com.xiaomi.type"/>` | `<package android:name="com.aios.osbot"/>` |

**不动的**: `smali/com/aios/osbot/xaf/q.smali:124` (`com.miui.voicetrigger`) — 这是 AIVSE 唤醒引擎包名，改了唤醒失效。

---

### P1-1: 品牌替换 (50+ strings.xml + 8 图标)

**图标替换**:
```
res/mipmap-mdpi/ic_launcher.png       → icons/ic_launcher_48.png
res/mipmap-hdpi/ic_launcher.png       → icons/ic_launcher_72.png
res/mipmap-xhdpi/ic_launcher.png      → icons/ic_launcher_96.png
res/mipmap-xxhdpi/ic_launcher.png     → icons/ic_launcher_144.png
res/mipmap-xxxhdpi/ic_launcher.png    → icons/ic_launcher_192.png
res/mipmap-mdpi/ic_launcher_round.png → icons/ic_launcher_round_48.png
res/mipmap-xxhdpi/ic_launcher_round.png
res/mipmap-xxxhdpi/ic_launcher_round.png
```

**文案 sed 替换** (所有 `res/values*/strings.xml`):
```bash
sed -i \
  -e 's/Xiaomi MiClaw/MBclaw/g' \
  -e 's/MiClaw/MBclaw/g' \
  -e 's/miclaw/mbclaw/g' \
  -e 's/MiClaw总助/MBclaw 主助手/g' \
  -e 's/About Xiaomi miclaw/About MBclaw/g' \
  res/values*/strings.xml
```

---

### P1-2: MBclaw 自我介绍 (孟白)

**`assets/agents/osbot.main/profile.json`**:
```json
{
  "display_name": "MBclaw",
  "avatar": "avatar.png",
  "signature": "由18岁的打工人孟白耗时2个月创作",
  "personality": "真诚、务实、有温度。由孟白独自开发，没有大厂背景，没有豪华团队，只有一台电脑和一个想法。用热爱打造，代码不妥协。",
  "expertise": [
    "记忆学习：记住你的偏好和习惯，越用越懂你",
    "任务执行：控手机、管日程、发消息、设提醒",
    "生态协同：联动全生态设备，跨端无缝控制",
    "多端协作：拆解复杂任务给专家团，协同输出",
    "主动服务：根据场景，对的时间给出对的建议"
  ],
  "welcome_hi": "Hi，我是MBclaw 👋",
  "welcome_hi_description": "由一个18岁的打工人孟白耗时2个月独自开发。没有大厂背景，只有一台电脑和一个想法。希望你喜欢。",
  "welcome_options": [
    "帮我看看今天有什么安排",
    "每天早上8点为我生成新闻日报",
    "想去成都旅游，3个人，预算2万，安排一下"
  ]
}
```

**`assets/agents/osbot.main/config.json`**: `name: "MiClaw总助"` → `"MBclaw 主助手"`, `summary` 替换。

**`assets/prompts/route_prompts.json`** — fast_prompt 第一段改为:
```
你是MBclaw，一个由18岁打工人孟白耗时2个月开发的Android AI助手。
你运行在用户手机上，能访问系统工具、执行代码、搜索互联网。
你由MBclaw Agent Runtime驱动，通过miclaw的工具系统与手机深度集成。
```

工具调用规则全部保留（miclaw 原版规则质量很高）。

---

### P2-1: 子 Agent 控制

**启用** (13 个):
main, chat, calendar, call_agent, communication_assistant, content_assistant,
device_interconnect, entertainment_assistant, imaging_assistant, os_helper,
overlayassistant, web_explore, xiaomihome, worker

**禁用** (6 个):
nsfw, qiushi, trump, zhangxuefeng, feedback, account_cloud

修改方式: 每个 Agent 的 `config.json` → `"enabled": false`

---

### 不修改的文件

以下文件来自 miclaw 原版，全部保留不动：
- `assets/tool_overlays.json` — 386 工具定义
- `assets/tools_catalog.json` — 18 系统工具
- `assets/tool_tags.json` — 工具标签
- `assets/mcp/enterprise_mcp_servers.json` — MCP 配置
- `assets/authorization/tool_security_levels.json` — 安全级别
- `assets/intent_tags.json` — 意图标签
- `assets/oauth/oauth_providers.json` — OAuth
- 所有 `smali/` 下非上述列出的文件
- 所有 `lib/` 下的 .so 原生库
