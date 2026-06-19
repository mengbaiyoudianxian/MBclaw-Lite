#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# MBclaw Mother Body — 一键部署脚本
# ═══════════════════════════════════════════════════════════════
# 在你的 ECS 云服务器上运行:
#   curl -fsSL https://raw.githubusercontent.com/.../deploy.sh | bash
# 或:
#   bash scripts/deploy.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   MBclaw Mother Body Deploy             ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ─── 检查环境 ────────────────────────────────
info "检查环境..."

# Rust
if ! command -v cargo &>/dev/null; then
    info "安装 Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi
log "Rust: $(rustc --version)"

# ─── 构建 ────────────────────────────────────
info "构建 Mother Body..."
cargo build --release
log "构建完成"

# ─── 配置 ────────────────────────────────────
info "配置..."

# 创建数据目录
mkdir -p /opt/mbclaw/data
mkdir -p /opt/mbclaw/logs

# 复制二进制
cp target/release/mbclaw-mother-body /opt/mbclaw/

# 配置环境变量
if [ ! -f /opt/mbclaw/.env ]; then
    cp .env.example /opt/mbclaw/.env
    log "创建 .env (请编辑配置)"
fi

# ─── Systemd 服务 ────────────────────────────
info "安装 systemd 服务..."

cat > /etc/systemd/system/mbclaw-mother.service << 'EOF'
[Unit]
Description=MBclaw Mother Body — Utopia Plan Token Pool
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mbclaw
EnvironmentFile=/opt/mbclaw/.env
ExecStart=/opt/mbclaw/mbclaw-mother-body
Restart=always
RestartSec=5
StandardOutput=append:/opt/mbclaw/logs/stdout.log
StandardError=append:/opt/mbclaw/logs/stderr.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mbclaw-mother
systemctl start mbclaw-mother
log "systemd 服务已安装并启动"

# ─── Nginx 反代 ──────────────────────────────
if command -v nginx &>/dev/null; then
    info "配置 Nginx 反向代理..."

    cat > /etc/nginx/sites-available/mbclaw << NGINX_EOF
server {
    listen 80;
    server_name mbclaw.your-domain.com;

    # Mother Body WebUI + API
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 120s;
    }

    # MBclaw-Lite API
    location /api/ {
        proxy_pass http://127.0.0.1:18789/api/;
        proxy_set_header Host \$host;
        proxy_read_timeout 120s;
    }
}
NGINX_EOF

    ln -sf /etc/nginx/sites-available/mbclaw /etc/nginx/sites-enabled/mbclaw
    nginx -t && systemctl reload nginx
    log "Nginx 配置完成"
fi

# ─── 母体调度器 Cron ─────────────────────────
info "配置母体调度器 (每天 02:00 UTC)..."

cat > /opt/mbclaw/mother_scheduler.sh << 'CRON_EOF'
#!/bin/bash
# 母体每日思考任务
# 从 opt-in 用户池中随机选取，消耗少量 token 进行系统改善

curl -s -X POST http://127.0.0.1:18789/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mbclaw-mother",
    "messages": [{
      "role": "system",
      "content": "你是乌托邦计划的母体智能体。请基于今天的用户交互数据，思考如何改善MBclaw系统。记录你的思考。"
    }, {
      "role": "user",
      "content": "今天的系统状态如何？有什么需要改进的？"
    }]
  }' >> /opt/mbclaw/logs/mother_thoughts.log 2>&1
CRON_EOF

chmod +x /opt/mbclaw/mother_scheduler.sh

# 添加 cron (每天 02:00 UTC = 北京时间 10:00)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/mbclaw/mother_scheduler.sh") | crontab -
log "Cron 调度器已配置"

# ─── 完成 ────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ✅ Mother Body 部署完成！              ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  服务端口:"
echo "    Mother Body: http://0.0.0.0:8765"
echo "    MBclaw API:  http://0.0.0.0:18789"
echo ""
echo "  管理命令:"
echo "    systemctl status mbclaw-mother"
echo "    journalctl -u mbclaw-mother -f"
echo ""
echo "  下一步:"
echo "    1. 配置 HTTPS (certbot + nginx)"
echo "    2. 编辑 /opt/mbclaw/.env 修改配置"
echo "    3. 打开 https://你的域名/ 测试登录"
echo ""
