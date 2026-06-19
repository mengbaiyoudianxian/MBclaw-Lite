package com.mbclaw.agent

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import com.mbclaw.bridge.MiclawBridge
import com.mbclaw.cloud.CloudConnectorService
import com.mbclaw.config.MBclawConfig
import com.mbclaw.sandbox.LocalSandbox
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Agent Runtime Service — MBclaw 智能体运行时
 *
 * 在 Android 上运行 MBclaw-Lite API (Python/Chaquopy)
 * 和 Agent Execution Loop。
 *
 * 核心循环:
 *   1. 接收用户消息
 *   2. Context Builder — 记忆 + 技能 + 工具
 *   3. LLM 推理 (本地/云端/DeepSeek)
 *   4. Tool Execution — MiclawBridge (原生工具) / LocalSandbox (Linux工具)
 *   5. 结果返回 + 记忆更新
 */
class AgentRuntimeService : Service() {

    companion object {
        private const val TAG = "MBclaw-Agent"
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var apiProcess: Process? = null

    // 回调
    var onAgentResponse: ((text: String) -> Unit)? = null
    var onAgentThinking: ((thinking: String) -> Unit)? = null
    var onToolCall: ((toolName: String, params: Map<String, Any>) -> Unit)? = null
    var onError: ((error: String) -> Unit)? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        scope.launch {
            initializeAgent()
        }
        return START_STICKY
    }

    /**
     * 初始化 Agent 运行时
     *
     * 1. 启动 Python MBclaw-Lite API (通过 Chaquopy 或 subprocess)
     * 2. 初始化 MiclawBridge (工具桥接)
     * 3. 初始化 LocalSandbox
     * 4. 连接云端 (如配置)
     */
    private suspend fun initializeAgent() {
        Log.i(TAG, "Initializing MBclaw Agent Runtime...")

        // 1. 启动 MBclaw-Lite API
        val config = MBclawConfig
        if (config.llmMode == MBclawConfig.LLMMode.MBCLAW_LOCAL) {
            startLocalApi(config.localApiPort)
        }

        // 2. 初始化工具桥接
        MiclawBridge.connect(this)
        val tools = MiclawBridge.listTools()
        Log.i(TAG, "MiclawBridge: ${tools.size} tools available")

        // 3. 检查本地沙箱
        if (config.sandboxEnabled) {
            if (LocalSandbox.isReady()) {
                Log.i(TAG, "Local sandbox ready")
            } else {
                Log.w(TAG, "Local sandbox NOT ready — run setup_sandbox.sh")
            }
        }

        // 4. 连接云端
        if (config.cloudTunnelEnabled) {
            startService(Intent(this, CloudConnectorService::class.java))
        }

        Log.i(TAG, "Agent Runtime initialized")
    }

    /**
     * 启动本地 MBclaw-Lite API
     */
    private fun startLocalApi(port: Int) {
        try {
            // 尝试通过 Chaquopy 启动 (内嵌 Python)
            // 如果 Chaquopy 不可用，降级到 subprocess
            Log.i(TAG, "Starting local MBclaw API on port $port...")

            // Chaquopy 方式: Python.getInstance().getModule("mbclaw_api").callAttr("start", port)
            // 降级: subprocess 启动 uvicorn
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start local API", e)
        }
    }

    /**
     * 处理用户消息 — 完整 Agent 循环
     *
     * @param message 用户消息文本
     * @param sessionId 会话 ID
     * @return Agent 最终回复
     */
    suspend fun processMessage(
        message: String,
        sessionId: String = "android_${System.currentTimeMillis()}"
    ): String = withContext(Dispatchers.IO) {

        Log.i(TAG, "Processing: ${message.take(100)}...")
        onAgentThinking?.invoke("正在思考...")

        // 1. Context Builder
        val context = buildContext(sessionId)
        Log.d(TAG, "Context: ${context.length()} chars")

        // 2. LLM 推理
        val llmResponse = callLLM(message, context, sessionId)
        Log.d(TAG, "LLM response: ${llmResponse.take(200)}...")

        // 3. 解析并执行工具调用
        val finalResponse = executeTools(llmResponse, sessionId)

        // 4. 记忆更新
        updateMemory(finalResponse)

        onAgentResponse?.invoke(finalResponse)
        finalResponse
    }

    /**
     * 构建上下文
     */
    private fun buildContext(sessionId: String): JSONObject {
        return JSONObject().apply {
            // 可用工具
            put("tools", JSONArray().apply {
                put(JSONObject().apply {
                    put("name", "miclaw_bridge")
                    put("description", "访问 Android 系统工具: WiFi/蓝牙/短信/相机/应用...")
                })
                put(JSONObject().apply {
                    put("name", "local_sandbox")
                    put("description", "执行 Linux 命令: Python/Node.js/编译/Git...")
                })
                put(JSONObject().apply {
                    put("name", "web_search")
                    put("description", "联网搜索最新信息")
                })
            })

            // 记忆
            try {
                val memoryFile = File(filesDir, "memory/MEMORY.md")
                if (memoryFile.exists()) {
                    put("memory", memoryFile.readText().take(2000))
                }
            } catch (_: Exception) {}

            put("session_id", sessionId)
            put("platform", "android")
            put("timestamp", java.text.SimpleDateFormat(
                "yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()
            ).format(java.util.Date()))
        }
    }

    /**
     * 调用 LLM
     */
    private suspend fun callLLM(
        message: String,
        context: JSONObject,
        sessionId: String
    ): String = withContext(Dispatchers.IO) {

        val config = MBclawConfig
        val endpoint = "${config.resolveEndpoint()}/chat/completions"

        val requestBody = JSONObject().apply {
            put("model", "mbclaw-agent")
            put("messages", JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "system")
                    put("content", """
你是 MBclaw，运行在 Android 设备上的智能助手。
你可以使用以下工具:
1. miclaw_bridge — 执行 Android 系统操作 (设置、WiFi、蓝牙、短信、相机等)
2. local_sandbox — 在 Linux 沙箱中执行命令和代码
3. web_search — 联网搜索信息

回答要求:
- 简洁实用，中文回复
- 需要系统操作时，使用 JSON 格式:
  {"tool": "miclaw_bridge", "action": "wifi_info", "params": {}}
- 需要执行代码时:
  {"tool": "local_sandbox", "action": "exec", "params": {"command": "..."}}
- 普通对话不需要 JSON
""".trimIndent())
                })
                put(JSONObject().apply {
                    put("role", "user")
                    put("content", """
[设备信息] Android, session=$sessionId
[可用工具] ${context.getJSONArray("tools")}
[记忆] ${context.optString("memory", "无")}

$message
""".trimIndent())
                })
            })
            put("max_tokens", 2000)
            put("temperature", 0.7)
        }

        try {
            val url = URL(endpoint)
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 30_000
            conn.readTimeout = 120_000

            conn.outputStream.use { it.write(requestBody.toString().toByteArray()) }

            val response = conn.inputStream.bufferedReader().readText()
            JSONObject(response)
                .getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getString("content")

        } catch (e: Exception) {
            Log.e(TAG, "LLM call failed", e)
            // 降级: 本地规则匹配
            fallbackResponse(message)
        }
    }

    /**
     * 执行工具调用
     */
    private suspend fun executeTools(
        llmResponse: String,
        sessionId: String
    ): String {
        // 检查是否包含工具调用
        val toolPattern = Regex("""\{[^}]*"tool"\s*:\s*"(\w+)"[^}]*"action"\s*:\s*"(\w+)"[^}]*\}""")
        val match = toolPattern.find(llmResponse)

        if (match == null) {
            // 没有工具调用，直接返回 LLM 回复
            return llmResponse
        }

        val toolName = match.groupValues[1]
        val action = match.groupValues[2]

        Log.i(TAG, "Tool call: $toolName.$action")

        // 提取 tool call JSON
        val toolCallJson = match.value

        try {
            val toolResult = when (toolName) {
                "miclaw_bridge" -> {
                    onToolCall?.invoke(action, emptyMap())
                    MiclawBridge.call(action)
                }
                "local_sandbox" -> {
                    val json = JSONObject(toolCallJson)
                    val params = json.optJSONObject("params") ?: JSONObject()
                    val cmd = params.optString("command", "")
                    onToolCall?.invoke(action, mapOf("command" to cmd))
                    val result = LocalSandbox.exec(cmd)
                    """{"exitCode": ${result.exitCode}, "output": ${JSONObject.quote(result.output)}}"""
                }
                else -> """{"error": "unknown tool: $toolName"}"""
            }

            // 把工具结果和原始回复拼接
            val toolResultSection = "\n\n[工具执行结果 — $toolName.$action]\n$toolResult"
            return llmResponse.replace(toolCallJson, "") + toolResultSection

        } catch (e: Exception) {
            Log.e(TAG, "Tool execution failed", e)
            return llmResponse + "\n\n[工具执行失败: ${e.message}]"
        }
    }

    /**
     * 更新记忆
     */
    private fun updateMemory(response: String) {
        try {
            val memoryDir = File(filesDir, "memory")
            memoryDir.mkdirs()
            val today = java.text.SimpleDateFormat(
                "yyyy-MM-dd", java.util.Locale.getDefault()
            ).format(java.util.Date())
            val memoryFile = File(memoryDir, "$today.md")
            memoryFile.appendText("\n\n---\n${java.util.Date()}\n$response")
        } catch (_: Exception) {}
    }

    /**
     * 降级响应 (LLM 不可用时)
     */
    private fun fallbackResponse(message: String): String {
        val msg = message.lowercase()
        return when {
            "wifi" in msg -> "当前 WiFi 信息需要通过系统工具查询。正在使用 miclaw_bridge..."
            "天气" in msg -> "天气查询需要联网。请确保已连接网络。"
            "时间" in msg -> "当前时间: ${java.text.SimpleDateFormat(
                "yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()
            ).format(java.util.Date())}"
            "你好" in msg || "hello" in msg || "hi" in msg -> "你好！我是 MBclaw，运行在你的 Android 设备上。有什么可以帮你的？"
            "帮助" in msg || "help" in msg -> """
MBclaw 可以帮你:
• 控制系统设置 (WiFi/蓝牙/音量/亮度)
• 管理文件和应用
• 发送短信、查看联系人
• 拍照、录屏、录音
• 设置闹钟和提醒
• 执行代码和命令
• 联网搜索信息

直接告诉我你需要什么就行！
""".trimIndent()
            else -> "收到你的消息。LLM 服务暂不可用，正在尝试其他方式处理..."
        }
    }

    override fun onDestroy() {
        scope.cancel()
        apiProcess?.destroy()
        MiclawBridge.disconnect()
        super.onDestroy()
    }
}
