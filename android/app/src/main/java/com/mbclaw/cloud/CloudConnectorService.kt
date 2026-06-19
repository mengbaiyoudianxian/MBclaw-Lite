package com.mbclaw.cloud

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import kotlinx.coroutines.*
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI

/**
 * Cloud Connector Service — 云端链路
 *
 * 建立手机与 ECS 云端服务器之间的双向 WebSocket 隧道。
 * 无需 VPN — 通过 WebSocket 加密隧道实现内网穿透。
 *
 * 方案优先级:
 *   1. Cloudflare Tunnel (cloudflared) — 免费、自动 HTTPS
 *   2. frp (内网穿透) — 自建服务器
 *   3. 直连 — 公网 IP (不推荐)
 *
 * 使用场景:
 *   - 手机算力/存储不够 → 转发到云端 GPU 推理
 *   - 多设备协作 → 云端统一记忆/向量库
 *   - 远程访问 → 手机端 Agent 对外暴露 API
 */
class CloudConnectorService : Service() {

    companion object {
        private const val TAG = "MBclaw-Cloud"
        private const val RECONNECT_DELAY_MS = 5_000L
        private const val MAX_RECONNECT_DELAY_MS = 60_000L
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var wsClient: WebSocketClient? = null
    private var reconnectAttempts = 0
    private var isConnected = false

    // 配置
    private var tunnelType: String = "cloudflare"
    private var serverUrl: String = ""
    private var localPort: Int = 18790

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        loadConfig()
        scope.launch { connect() }
        return START_STICKY
    }

    private fun loadConfig() {
        val prefs = getSharedPreferences("mbclaw_cloud", MODE_PRIVATE)
        tunnelType = prefs.getString("tunnel_type", "cloudflare") ?: "cloudflare"
        serverUrl = prefs.getString("server_url", "") ?: ""
        localPort = prefs.getInt("local_port", 18790)
    }

    /**
     * 建立 WebSocket 连接
     */
    private suspend fun connect() {
        if (serverUrl.isBlank()) {
            Log.i(TAG, "Cloud server not configured, skipping")
            return
        }

        val wsUrl = when (tunnelType) {
            "cloudflare" -> serverUrl  // wss://mbclaw.your-domain.com/ws
            "frp" -> serverUrl          // ws://frp-server:port/ws
            else -> serverUrl
        }

        wsClient = object : WebSocketClient(URI(wsUrl)) {

            override fun onOpen(handshakedata: ServerHandshake?) {
                Log.i(TAG, "Cloud connected: $wsUrl")
                isConnected = true
                reconnectAttempts = 0

                // 注册本机信息
                send("""{"type":"register","device":"android","port":$localPort}""")
            }

            override fun onMessage(message: String?) {
                message ?: return
                Log.d(TAG, "Cloud message: ${message.take(200)}")

                // 转发到本地 MBclaw API
                scope.launch {
                    forwardToLocalApi(message)
                }
            }

            override fun onClose(code: Int, reason: String?, remote: Boolean) {
                Log.w(TAG, "Cloud disconnected: $reason")
                isConnected = false
                scheduleReconnect()
            }

            override fun onError(ex: Exception?) {
                Log.e(TAG, "Cloud error", ex)
                isConnected = false
            }
        }

        try {
            wsClient?.connect()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect", e)
            scheduleReconnect()
        }
    }

    /**
     * 转发消息到本地 MBclaw API
     */
    private suspend fun forwardToLocalApi(message: String) = withContext(Dispatchers.IO) {
        try {
            val url = java.net.URL("http://127.0.0.1:$localPort/v1/chat/completions")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 30_000
            conn.readTimeout = 120_000

            conn.outputStream.use { it.write(message.toByteArray()) }
            val response = conn.inputStream.bufferedReader().readText()
            Log.d(TAG, "Local API response: ${response.take(200)}")

            // 回传给云端
            if (isConnected) {
                wsClient?.send(response)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Forward error", e)
        }
    }

    /**
     * 指数退避重连
     */
    private fun scheduleReconnect() {
        val delay = minOf(
            RECONNECT_DELAY_MS * (1L shl reconnectAttempts),
            MAX_RECONNECT_DELAY_MS
        )
        reconnectAttempts++

        scope.launch {
            delay(delay)
            if (!isConnected) {
                Log.i(TAG, "Reconnecting (attempt $reconnectAttempts)...")
                connect()
            }
        }
    }

    /**
     * 向云端发送消息
     */
    fun sendToCloud(message: String) {
        if (isConnected) {
            wsClient?.send(message)
        }
    }

    override fun onDestroy() {
        scope.cancel()
        wsClient?.close()
        super.onDestroy()
    }
}
