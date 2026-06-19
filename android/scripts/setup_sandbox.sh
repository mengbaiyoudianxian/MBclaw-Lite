#!/system/bin/sh
# ═══════════════════════════════════════════════════════════
# MBclaw Local Linux Sandbox Setup
# ═══════════════════════════════════════════════════════════
# 在 Android 上初始化完整 Linux 环境 (proot + Ubuntu rootfs)
#
# 使用方法:
#   su -c "bash setup_sandbox.sh"
#
# 需要:
#   - Root 权限
#   - 网络连接 (下载 rootfs)
#   - ~500MB 存储空间
# ═══════════════════════════════════════════════════════════

set -e

SANDBOX_DIR="/data/mbclaw/sandbox"
ROOTFS_DIR="$SANDBOX_DIR/rootfs"
SHARED_DIR="$SANDBOX_DIR/shared"
WORKSPACE_DIR="$SANDBOX_DIR/workspace"
ROOTFS_URL="https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.4-base-arm64.tar.gz"
ROOTFS_FILE="$SANDBOX_DIR/ubuntu-rootfs.tar.gz"

echo "╔════════════════════════════════════════╗"
echo "║   MBclaw Sandbox Setup                ║"
echo "╚════════════════════════════════════════╝"
echo ""

# ─── 检查 root ────────────────────────────────
if [ "$(id -u)" != "0" ]; then
    echo "[!] 需要 root 权限！请用 su -c 执行。"
    exit 1
fi

# ─── 创建目录结构 ────────────────────────────
echo "[1/6] 创建目录结构..."
mkdir -p "$ROOTFS_DIR" "$SHARED_DIR" "$WORKSPACE_DIR"
chmod 755 "$SANDBOX_DIR" "$ROOTFS_DIR" "$SHARED_DIR" "$WORKSPACE_DIR"
echo "  ✓ 完成"

# ─── 下载 rootfs ──────────────────────────────
echo "[2/6] 下载 Ubuntu 22.04 ARM64 rootfs..."

if [ -f "$ROOTFS_DIR/bin/bash" ]; then
    echo "  ✓ rootfs 已存在，跳过下载"
else
    if [ ! -f "$ROOTFS_FILE" ]; then
        # 先尝试 wget，失败则用 curl
        if command -v wget >/dev/null 2>&1; then
            wget -O "$ROOTFS_FILE" "$ROOTFS_URL" 2>&1 || {
                echo "  [!] wget 失败，尝试 curl..."
                curl -L -o "$ROOTFS_FILE" "$ROOTFS_URL"
            }
        else
            curl -L -o "$ROOTFS_FILE" "$ROOTFS_URL"
        fi
    fi

    echo "  → 解压 rootfs (可能需要几分钟)..."
    tar -xzf "$ROOTFS_FILE" -C "$ROOTFS_DIR"
    rm -f "$ROOTFS_FILE"
    echo "  ✓ rootfs 解压完成"
fi

# ─── 配置 DNS ─────────────────────────────────
echo "[3/6] 配置 DNS..."
echo "nameserver 8.8.8.8" > "$ROOTFS_DIR/etc/resolv.conf"
echo "nameserver 1.1.1.1" >> "$ROOTFS_DIR/etc/resolv.conf"
echo "  ✓ DNS 已配置"

# ─── 配置 apt 源 ─────────────────────────────
echo "[4/6] 配置 apt 源..."
cat > "$ROOTFS_DIR/etc/apt/sources.list" << 'EOF'
deb http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse
deb http://ports.ubuntu.com/ubuntu-ports jammy-updates main restricted universe multiverse
deb http://ports.ubuntu.com/ubuntu-ports jammy-security main restricted universe multiverse
EOF
echo "  ✓ apt 源已配置"

# ─── 安装基础包 ─────────────────────────────
echo "[5/6] 安装基础包..."
# 使用 chroot 安装包 (需要 proot 或完整 root)
# 如果有 proot 工具:
if command -v proot >/dev/null 2>&1; then
    proot -r "$ROOTFS_DIR" -b /dev -b /proc -b /sys /bin/bash -c "
        apt-get update -qq &&
        apt-get install -y -qq python3 python3-pip nodejs npm git curl wget build-essential vim
    " 2>&1 | tail -3
    echo "  ✓ 基础包安装完成"
else
    echo "  [!] proot 未安装。跳过 apt 安装。"
    echo "      基础 rootfs 已就绪，可手动 chroot 安装包。"
fi

# ─── 创建启动脚本 ───────────────────────────
echo "[6/6] 创建便捷脚本..."

# 启动沙箱终端
cat > "$SANDBOX_DIR/shell.sh" << 'SHELLEOF'
#!/system/bin/sh
# 在沙箱中打开 shell
SANDBOX_DIR="/data/mbclaw/sandbox"
if command -v proot >/dev/null 2>&1; then
    proot -r "$SANDBOX_DIR/rootfs" \
        -b /dev -b /proc -b /sys \
        -b /sdcard:/sdcard \
        -b "$SANDBOX_DIR/shared:/shared" \
        -w /workspace \
        /bin/bash
else
    # 降级: 直接用 rootfs 中的 bash
    export PATH="$SANDBOX_DIR/rootfs/usr/bin:$SANDBOX_DIR/rootfs/bin:/system/bin"
    export HOME=/root
    cd "$SANDBOX_DIR/workspace"
    "$SANDBOX_DIR/rootfs/bin/bash"
fi
SHELLEOF
chmod +x "$SANDBOX_DIR/shell.sh"

# 启动 Python REPL
cat > "$SANDBOX_DIR/python.sh" << 'PYEOF'
#!/system/bin/sh
/data/mbclaw/sandbox/rootfs/usr/bin/python3 "$@"
PYEOF
chmod +x "$SANDBOX_DIR/python.sh"

echo "  ✓ 脚本已创建"
echo ""

# ─── 验证 ────────────────────────────────────
echo "╔════════════════════════════════════════╗"
echo "║   Setup Complete!                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  沙箱位置: $SANDBOX_DIR"
echo "  进入终端: bash $SANDBOX_DIR/shell.sh"
echo "  运行Python: bash $SANDBOX_DIR/python.sh -c 'print(\"hello\")'"
echo "  共享目录: $SHARED_DIR (与 Android 双向共享)"
echo ""
echo "  测试命令:"
echo "    $SANDBOX_DIR/rootfs/usr/bin/python3 --version"
echo ""
