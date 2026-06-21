#!/bin/bash
# Claude 工作区拉文件脚本 — 把 47.83.2.188:/var/lib/mbclaw/uploads 拉到本地
# 用法: bash pull_uploads.sh [清理远端: --clean]
set -e
LOCAL=/root/MBclaw-uploads
mkdir -p "$LOCAL"

# 用 sshpass 同步 (rsync 优先, 没有就 scp)
if command -v rsync >/dev/null 2>&1; then
    sshpass -p '20070520@han' rsync -av --progress \
        -e "ssh -o StrictHostKeyChecking=no" \
        root@47.83.2.188:/var/lib/mbclaw/uploads/ "$LOCAL/"
else
    sshpass -p '20070520@han' scp -o StrictHostKeyChecking=no -r \
        root@47.83.2.188:/var/lib/mbclaw/uploads/* "$LOCAL/" 2>/dev/null || true
fi

echo ""
echo "=== 本地文件 ==="
ls -lh "$LOCAL"

if [ "$1" = "--clean" ]; then
    echo ""
    echo "清理远端..."
    sshpass -p '20070520@han' ssh -o StrictHostKeyChecking=no root@47.83.2.188 'rm -f /var/lib/mbclaw/uploads/*'
fi
