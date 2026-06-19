# MBclaw Android APK — 构建指南

## 快速开始

```bash
cd android/
bash scripts/build.sh
```

30 秒内生成 APK。

## 构建要求

| 工具 | 版本 | 安装 |
|------|------|------|
| JDK | 17+ | `apt install openjdk-17-jdk` |
| Android SDK | 35 | Android Studio 或 cmdline-tools |
| Gradle | 8.5+ | 自动下载 (gradle-wrapper) |
| Python | 3.11+ | Chaquopy 插件自动处理 |
| Android NDK | 27+ | SDK Manager 安装 |

## 手动构建

```bash
# 1. 设置环境
export ANDROID_HOME=/path/to/Android/Sdk
export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.0.12077973

# 2. 生成签名密钥 (仅首次)
keytool -genkey -v \
    -keystore mbclaw.keystore \
    -alias mbclaw \
    -keyalg RSA -keysize 2048 -validity 10000

# 3. 构建
./gradlew assembleRelease

# 4. 输出
ls app/build/outputs/apk/release/app-release.apk
```

## 安装到手机

```bash
# 方法1: 直接安装
adb install app/build/outputs/apk/release/app-release.apk

# 方法2: 如果签名冲突 (核心破解)
adb install -r -d app/build/outputs/apk/release/app-release.apk

# 方法3: 推送到手机后手动安装
adb push app/build/outputs/apk/release/app-release.apk /sdcard/
# 在手机上: 文件管理器 → 点击 APK → 安装
```

## 初始化沙箱

```bash
# 手机上 (需要 root)
su
cd /data/local/tmp
bash setup_sandbox.sh
```

## 初始化云端链路

```bash
# ECS 服务器上
bash scripts/setup_cloud.sh
```

## 开发模式

```bash
# Debug 构建 (更快的迭代)
./gradlew assembleDebug

# 查看日志
adb logcat -s MBclaw:* AndroidRuntime:E

# 清除数据重装
adb uninstall com.mbclaw.assistant
adb install app/build/outputs/apk/debug/app-debug.apk
```

## 自定义

### 更改 LLM 端点
编辑 `app/src/main/java/com/mbclaw/config/MBclawConfig.kt`，或通过应用内设置修改。

### 更改品牌
- 图标: `app/src/main/res/mipmap/ic_launcher.png`
- 配色: `app/src/main/res/values/colors.xml`
- 字符串: `app/src/main/res/values/strings.xml`

### 添加新工具
在 `MiclawBridge.kt` 的 MCP server 脚本中添加 tool handler:

```python
elif method == "tools/call":
    if tool_name == "your_new_tool":
        result = your_handler(tool_args)
```
