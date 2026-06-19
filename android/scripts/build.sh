#!/bin/bash
# MBclaw Android APK — 30 秒构建脚本
# 使用方法: cd android && bash scripts/build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

cd "$PROJECT_DIR"

# ─── 检查环境 ────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     MBclaw Android APK Builder      ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Java
if ! command -v java &>/dev/null; then
    err "Java 未安装。请安装 JDK 17+: apt install openjdk-17-jdk"
    exit 1
fi
log "Java: $(java -version 2>&1 | head -1)"

# Android SDK
if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
    warn "ANDROID_HOME 未设置，尝试自动检测..."
    if [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
        log "检测到 Android SDK: $ANDROID_HOME"
    else
        err "Android SDK 未找到。请安装 Android Studio 或设置 ANDROID_HOME。"
        exit 1
    fi
fi

# ─── 构建 ────────────────────────────────────
info "开始构建..."

# 检查 keystore
if [ ! -f "mbclaw.keystore" ]; then
    warn "生成签名密钥..."
    keytool -genkey -v \
        -keystore mbclaw.keystore \
        -alias mbclaw \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -storepass mbclaw2024 \
        -keypass mbclaw2024 \
        -dname "CN=MBclaw, OU=Dev, O=MBclaw, L=Beijing, ST=Beijing, C=CN" \
        2>/dev/null
    log "密钥已生成: mbclaw.keystore"
fi

# Gradle 构建
info "运行 Gradle 构建..."

if [ -f "./gradlew" ]; then
    ./gradlew assembleRelease
else
    # 使用系统 Gradle
    gradle assembleRelease
fi

# ─── 输出 ────────────────────────────────────
APK="app/build/outputs/apk/release/app-release.apk"

if [ -f "$APK" ]; then
    SIZE=$(du -h "$APK" | cut -f1)
    log "构建成功！"
    echo ""
    echo "  APK: $APK"
    echo "  大小: $SIZE"
    echo ""
    echo "  安装命令:"
    echo "    adb install $APK"
    echo ""
    echo "  如果签名验证失败:"
    echo "    adb install -r -d $APK  # (-d 允许降级, -r 覆盖)"
    echo ""
else
    err "构建失败。检查上面的错误信息。"
    exit 1
fi
