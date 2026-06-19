#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# MBclaw APK Patcher — 一键: 解包→修改→重打包→签名
# ═══════════════════════════════════════════════════════════════
# 用法: bash patch_and_build.sh <魔改版带sese.apk> [cloud_host]
#
# 输入: miclaw 魔改版带sese.apk
# 输出: mbclaw-release.apk
#
# 需要: apktool, apksigner, zipalign, keytool, Java 17+
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ─── 参数 ────────────────────────────────────
APK_INPUT="${1:-}"
CLOUD_HOST="${2:-mbclaw.your-server.com}"

if [ -z "$APK_INPUT" ]; then
    echo "用法: bash patch_and_build.sh <魔改版带sese.apk> [cloud_host]"
    echo ""
    echo "示例:"
    echo "  bash patch_and_build.sh ../miclaw-apks/魔改版带sese.apk"
    echo "  bash patch_and_build.sh ../miclaw-apks/魔改版带sese.apk mbclaw.example.com"
    exit 1
fi

if [ ! -f "$APK_INPUT" ]; then
    err "APK 文件不存在: $APK_INPUT"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$SCRIPT_DIR/work"
CONFIGS_DIR="$SCRIPT_DIR/configs"
ICONS_DIR="$SCRIPT_DIR/icons"
OUTPUT_APK="$SCRIPT_DIR/mbclaw-release.apk"
KEYSTORE="$SCRIPT_DIR/mbclaw.keystore"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     MBclaw APK Patcher v1.0              ║"
echo "  ║     miclaw → MBclaw 一键改造             ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
info "输入: $APK_INPUT"
info "云端: $CLOUD_HOST"

# ─── 清理 ────────────────────────────────────
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

# ─── 步骤 1/6: 解包 ──────────────────────────
info "[1/6] apktool 解包..."
apktool d -f "$APK_INPUT" -o "$WORK_DIR/unpacked" 2>&1 | tail -1
log "解包完成"

UNPACKED="$WORK_DIR/unpacked"

# ─── 步骤 2/6: API 端点 + 语音路由 smali ─────
info "[2/6] smali 修改 — API端点 + 语音路由..."

# 2a. API 端点 — smali_classes3/kn/g.smali:2060
TARGET="$UNPACKED/smali_classes3/kn/g.smali"
if [ -f "$TARGET" ]; then
    sed -i 's|https://api.mify.mioffice.cn/v1/chat/completions|https://'"$CLOUD_HOST"'/v1/chat/completions|g' "$TARGET"
    log "  API端点 #1: kn/g.smali"
else
    warn "  smali_classes3/kn/g.smali 不存在，跳过"
fi

# 2b. 备用端点 — 3个文件
for f in \
    "$UNPACKED/smali/com/aios/osbot/data/repository/c2.smali" \
    "$UNPACKED/smali/v9/x.smali" \
    "$UNPACKED/smali/v9/f0.smali"
do
    if [ -f "$f" ]; then
        sed -i 's|https://api.miclaw.xiaomi.net/llm-proxy/mify/v1|https://'"$CLOUD_HOST"'/v1|g' "$f"
        log "  API端点: $(basename $(dirname $f))/$(basename $f)"
    fi
done

# 2c. 语音路由 — trigger_router_config.json
if [ -f "$UNPACKED/assets/trigger_router_config.json" ]; then
    cp "$CONFIGS_DIR/assets/trigger_router_config.json" "$UNPACKED/assets/trigger_router_config.json"
    log "  语音路由: trigger_router_config.json → MBclaw"
fi

# 2d. 语音路由 — q.smali (voiceassist -> osbot)
Q_SMALI="$UNPACKED/smali/com/aios/osbot/xaf/q.smali"
if [ -f "$Q_SMALI" ]; then
    sed -i 's|const-string v5, "com.miui.voiceassist"|const-string v5, "com.aios.osbot"|g' "$Q_SMALI"
    log "  语音路由: q.smali voiceassist → osbot"
fi

# 2e. 语音路由 — vb/o.smali (xiaomi.type -> osbot)
O_SMALI="$UNPACKED/smali/vb/o.smali"
if [ -f "$O_SMALI" ]; then
    sed -i 's|const-string v5, "com.xiaomi.type"|const-string v5, "com.aios.osbot"|g' "$O_SMALI"
    log "  语音路由: o.smali xiaomi.type → osbot"
fi

# 2f. AndroidManifest — queries 区
MANIFEST="$UNPACKED/AndroidManifest.xml"
if [ -f "$MANIFEST" ]; then
    sed -i 's|<package android:name="com.xiaomi.type"/>|<package android:name="com.aios.osbot"/>|g' "$MANIFEST"
    log "  Manifest queries: com.xiaomi.type → com.aios.osbot"
fi

# ─── 步骤 3/6: 品牌替换 ──────────────────────
info "[3/6] 品牌替换 — 文案 + 图标 + Agent身份..."

# 3a. 所有 strings.xml
STRINGS_COUNT=0
for f in "$UNPACKED/res/values"*/strings.xml; do
    if [ -f "$f" ]; then
        sed -i \
            -e 's/Xiaomi MiClaw/MBclaw/g' \
            -e 's/MiClaw/MBclaw/g' \
            -e 's/miclaw/mbclaw/gI' \
            -e 's/MiClaw总助/MBclaw 主助手/g' \
            -e 's/About Xiaomi miclaw/About MBclaw/g' \
            "$f"
        STRINGS_COUNT=$((STRINGS_COUNT + 1))
    fi
done
log "  文案替换: $STRINGS_COUNT 个 strings.xml"

# 3b. 替换图标
if [ -d "$ICONS_DIR" ]; then
    # mipmap 目录映射
    for dir in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
        ICON_SRC="$ICONS_DIR/ic_launcher_${dir}.png"
        ICON_DST="$UNPACKED/res/mipmap-${dir}/ic_launcher.png"
        ROUND_DST="$UNPACKED/res/mipmap-${dir}/ic_launcher_round.png"

        if [ -f "$ICON_SRC" ] && [ -d "$(dirname "$ICON_DST")" ]; then
            cp "$ICON_SRC" "$ICON_DST"
            if [ -f "$ROUND_DST" ] || [ -d "$(dirname "$ROUND_DST")" ]; then
                cp "$ICON_SRC" "$ROUND_DST" 2>/dev/null || true
            fi
        fi
    done
    log "  图标替换完成"
else
    warn "  图标目录不存在，跳过 ($ICONS_DIR)"
fi

# 3c. Agent 身份 — profile.json
MAIN_PROFILE="$UNPACKED/assets/agents/osbot.main/profile.json"
if [ -f "$MAIN_PROFILE" ]; then
    cp "$CONFIGS_DIR/agents/osbot.main/profile.json" "$MAIN_PROFILE"
    log "  Agent身份: profile.json → 孟白"
fi

# 3d. Agent 名称 — config.json
MAIN_CONFIG="$UNPACKED/assets/agents/osbot.main/config.json"
if [ -f "$MAIN_CONFIG" ]; then
    cp "$CONFIGS_DIR/agents/osbot.main/config.json" "$MAIN_CONFIG"
    log "  Agent配置: config.json → MBclaw主助手"
fi

# 3e. System Prompt
ROUTE_PROMPTS="$UNPACKED/assets/prompts/route_prompts.json"
if [ -f "$ROUTE_PROMPTS" ]; then
    cp "$CONFIGS_DIR/assets/prompts/route_prompts.json" "$ROUTE_PROMPTS"
    log "  SystemPrompt: route_prompts.json → MBclaw"
fi

# ─── 步骤 4/6: 子Agent 禁用 ──────────────────
info "[4/6] 子Agent 管理..."

DISABLED_COUNT=0
for agent in osbot.nsfw osbot.qiushi osbot.trump osbot.zhangxuefeng osbot.feedback osbot.account_cloud; do
    AGENT_CONF="$UNPACKED/assets/agents/$agent/config.json"
    if [ -f "$AGENT_CONF" ]; then
        # 用 sed 把 "enabled": true 改成 false
        sed -i 's/"enabled"\s*:\s*true/"enabled": false/g' "$AGENT_CONF"
        DISABLED_COUNT=$((DISABLED_COUNT + 1))
        log "  禁用: $agent"
    fi
done
log "  共禁用 $DISABLED_COUNT 个 Agent"

# ─── 步骤 5/6: 网络配置 ──────────────────────
info "[5/6] 网络配置..."

# 替换 network_security_config.xml
NSC="$UNPACKED/res/xml/network_security_config.xml"
if [ -f "$NSC" ]; then
    sed -i "s|CLOUD_HOST_PLACEHOLDER|$CLOUD_HOST|g" "$CONFIGS_DIR/assets/network_security_config.xml"
    cp "$CONFIGS_DIR/assets/network_security_config.xml" "$NSC"
    log "  网络安全配置已更新"
fi

# ─── 步骤 6/6: 重打包 + 签名 ──────────────────
info "[6/6] 重打包 + 签名..."

# 6a. apktool 重打包
apktool b "$UNPACKED" -o "$WORK_DIR/mbclaw-unsigned.apk" 2>&1 | tail -1
log "重打包完成"

# 6b. 生成密钥 (首次)
if [ ! -f "$KEYSTORE" ]; then
    info "  生成签名密钥..."
    keytool -genkey -v \
        -keystore "$KEYSTORE" \
        -alias mbclaw \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass mbclaw2024 -keypass mbclaw2024 \
        -dname "CN=MBclaw, OU=Dev, O=MBclaw, L=Beijing, ST=Beijing, C=CN" \
        2>/dev/null
fi

# 6c. zipalign
zipalign -v 4 "$WORK_DIR/mbclaw-unsigned.apk" "$WORK_DIR/mbclaw-aligned.apk" 2>&1 | tail -1
log "对齐完成"

# 6d. 签名
apksigner sign \
    --ks "$KEYSTORE" \
    --ks-pass pass:mbclaw2024 \
    --ks-key-alias mbclaw \
    --key-pass pass:mbclaw2024 \
    --out "$OUTPUT_APK" \
    "$WORK_DIR/mbclaw-aligned.apk" 2>&1
log "签名完成"

# ─── 输出 ────────────────────────────────────
SIZE=$(du -h "$OUTPUT_APK" | cut -f1)

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     ✅ MBclaw APK 构建完成！             ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  📦 $OUTPUT_APK"
echo "  📏 $SIZE"
echo ""
echo "  安装命令:"
echo "    adb install -r -d $OUTPUT_APK"
echo ""
echo "  ⚠️ 需要核心破解 (LSPosed + CorePatch) 跳过签名验证"
echo ""
