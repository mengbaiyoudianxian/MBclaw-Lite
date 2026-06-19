#!/bin/bash
# ═══════════════════════════════════════════════════════════
# MBclaw Cloud Tunnel Setup — 云端隧道初始化
# ═══════════════════════════════════════════════════════════
# 在 ECS 服务器上运行此脚本，配置与手机的 WebSocket 隧道
#
# 方案1: Cloudflare Tunnel (推荐 — 免费、自动 HTTPS、免公网IP)
# 方案2: frp (自建内网穿透)
# ═══════════════════════════════════════════════════════════
set -euo pipefail

echo "╔════════════════════════════════════════╗"
echo "║   MBclaw Cloud Tunnel Setup           ║"
echo "╚════════════════════════════════════════╝"
echo ""

# ─── 选择方案 ────────────────────────────────
echo "选择隧道方案:"
echo "  1) Cloudflare Tunnel (推荐 — 免费)"
echo "  2) frp (自建)"
echo "  3) WebSocket 直连"
read -p "选择 [1-3]: " CHOICE

case "$CHOICE" in
    1)
        setup_cloudflare
        ;;
    2)
        setup_frp
        ;;
    3)
        setup_direct_ws
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

# ═════════════════════════════════════════════
# Cloudflare Tunnel
# ═════════════════════════════════════════════
setup_cloudflare() {
    echo ""
    echo "[Cloudflare Tunnel Setup]"

    # 安装 cloudflared
    if ! command -v cloudflared &>/dev/null; then
        echo "安装 cloudflared..."
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
            -o /usr/local/bin/cloudflared
        chmod +x /usr/local/bin/cloudflared
    fi

    # 登录
    echo ""
    echo "请在浏览器打开 Cloudflare Zero Trust Dashboard:"
    echo "  https://one.dash.cloudflare.com/"
    echo ""
    echo "Networks → Tunnels → Create Tunnel"
    echo "选择 'Cloudflared' → 复制 Tunnel Token"
    echo ""
    read -p "粘贴 Tunnel Token: " TOKEN

    # 安装为系统服务
    cloudflared service install "$TOKEN"

    # 配置 ingress
    cat > ~/.cloudflared/config.yml << 'CFEOF'
tunnel: <your-tunnel-id>
credentials-file: /root/.cloudflared/<your-tunnel-id>.json

ingress:
  # MBclaw WebSocket
  - hostname: mbclaw.your-domain.com
    service: ws://localhost:18790

  # 健康检查
  - hostname: mbclaw-health.your-domain.com
    service: http_status:200

  # 默认 404
  - service: http_status:404
CFEOF

    echo ""
    echo "Cloudflare Tunnel 已安装!"
    echo "手机端配置:"
    echo "  cloud_tunnel_enabled = true"
    echo "  tunnel_type = cloudflare"
    echo "  server_url = wss://mbclaw.your-domain.com/ws"
    echo ""
    echo "或使用 Cloudflare WARP (更轻量):"
    echo "  https://1.1.1.1/"
}

# ═════════════════════════════════════════════
# frp (内网穿透)
# ═════════════════════════════════════════════
setup_frp() {
    echo ""
    echo "[frp Setup]"

    FRP_VERSION="0.61.0"
    FRP_DIR="/opt/frp"

    if [ ! -f "$FRP_DIR/frps" ]; then
        echo "下载 frp $FRP_VERSION..."
        wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
        tar -xzf "frp_${FRP_VERSION}_linux_amd64.tar.gz"
        mkdir -p "$FRP_DIR"
        cp "frp_${FRP_VERSION}_linux_amd64/frps" "$FRP_DIR/"
        cp "frp_${FRP_VERSION}_linux_amd64/frpc" "$FRP_DIR/"
        rm -rf "frp_${FRP_VERSION}_linux_amd64"*
    fi

    # frps 服务端配置
    cat > "$FRP_DIR/frps.toml" << 'FRPEOF'
bindPort = 7000
auth.token = "mbclaw-frp-token-change-me"

# WebSocket 端口转发
vhostHTTPPort = 8080

# 日志
log.to = "/var/log/frps.log"
log.level = "info"
FRPEOF

    # 手机端 frpc 配置
    mkdir -p "$FRP_DIR/client/"
    cat > "$FRP_DIR/client/frpc.toml" << 'FRPCEOF'
# ─── 手机端配置 (复制到 /data/mbclaw/frp/frpc.toml) ───
serverAddr = "YOUR_ECS_IP"
serverPort = 7000
auth.token = "mbclaw-frp-token-change-me"

[[proxies]]
name = "mbclaw-api"
type = "tcp"
localIP = "127.0.0.1"
localPort = 18790
remotePort = 18790

[[proxies]]
name = "mbclaw-ws"
type = "tcp"
localIP = "127.0.0.1"
localPort = 18791
remotePort = 18791
FRPCEOF

    # 启动 frps
    "$FRP_DIR/frps" -c "$FRP_DIR/frps.toml" &
    echo "frps 已启动 (端口 7000)"

    echo ""
    echo "手机端配置:"
    echo "  cloud_tunnel_enabled = true"
    echo "  tunnel_type = frp"
    echo "  server_url = ws://YOUR_ECS_IP:18791/ws"
    echo ""
    echo "将 $FRP_DIR/client/frpc.toml 复制到手机 /data/mbclaw/frp/"
}

# ═════════════════════════════════════════════
# WebSocket 直连
# ═════════════════════════════════════════════
setup_direct_ws() {
    echo ""
    echo "[WebSocket 直连 Setup]"

    echo "使用 Python websockets 库启动中继服务器:"
    pip3 install websockets 2>/dev/null || true

    cat > /opt/mbclaw-ws-relay.py << 'PYEOF'
#!/usr/bin/env python3
"""MBclaw WebSocket Relay — 云端中继服务器"""
import asyncio
import websockets
import json

CLIENTS = {}  # device_id -> websocket

async def handler(websocket, path):
    device_id = None
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "register":
                device_id = data.get("device", "unknown")
                CLIENTS[device_id] = websocket
                print(f"[+] Device registered: {device_id}")
                await websocket.send(json.dumps({"status": "registered", "device": device_id}))

            elif msg_type == "forward_to_device" and device_id:
                target = CLIENTS.get(data.get("target"))
                if target:
                    await target.send(json.dumps(data["payload"]))
                    response = await asyncio.wait_for(target.recv(), timeout=120)
                    await websocket.send(response)
                else:
                    await websocket.send(json.dumps({"error": "device not found"}))

            elif msg_type == "agent_request":
                # 转发到本机 MBclaw-Lite API
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:18789/v1/chat/completions",
                    data=json.dumps(data["payload"]).encode(),
                    headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=120)
                await websocket.send(resp.read().decode())

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if device_id and device_id in CLIENTS:
            del CLIENTS[device_id]
            print(f"[-] Device disconnected: {device_id}")

print("MBclaw WS Relay starting on ws://0.0.0.0:18790/ws")
asyncio.get_event_loop().run_until_complete(
    websockets.serve(handler, "0.0.0.0", 18790)
)
asyncio.get_event_loop().run_forever()
PYEOF

    chmod +x /opt/mbclaw-ws-relay.py
    echo ""
    echo "中继服务器已创建: /opt/mbclaw-ws-relay.py"
    echo "启动: python3 /opt/mbclaw-ws-relay.py &"
    echo ""
    echo "手机端配置:"
    echo "  cloud_tunnel_enabled = true"
    echo "  tunnel_type = direct"
    echo "  server_url = ws://YOUR_ECS_IP:18790/ws"
}

echo ""
echo "═" * 50
echo "Setup complete! 下一步:"
echo "  1. 在手机上部署 APK"
echo "  2. 在设置中启用云端连接"
echo "  3. 输入服务器地址"
echo "  4. 验证状态指示器变绿"
echo "═" * 50
