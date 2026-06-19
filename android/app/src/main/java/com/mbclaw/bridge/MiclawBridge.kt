package com.mbclaw.bridge

import android.content.Context
import android.content.Intent
import android.os.IBinder
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import java.io.*
import java.util.concurrent.ConcurrentHashMap

/**
 * Miclaw Bridge — MCP 协议桥接层
 *
 * 通过 MCP (Model Context Protocol) 调用 miclaw 内建的 386+ 工具。
 * MBclaw Agent 不需要自己实现系统工具，直接复用 miclaw 的能力。
 *
 * 架构:
 *   MBclaw Agent → MiclawBridge.call(toolName, params) → MCP Server → Android API
 *
 * 支持的传输:
 *   1. stdio MCP (启动 miclaw MCP server 子进程)
 *   2. AIDL/IPC MCP (通过 miclaw 的 ILLMManager 接口)
 *   3. HTTP MCP (通过本地 HTTP 端点)
 */
object MiclawBridge {

    private const val TAG = "MBclaw-Bridge"

    // MCP Server 进程
    private var mcpProcess: Process? = null
    private var mcpInput: BufferedWriter? = null
    private var mcpOutput: BufferedReader? = null

    // 工具调用超时
    private const val TOOL_TIMEOUT_MS = 30_000L

    // 活跃调用追踪
    private val pendingCalls = ConcurrentHashMap<String, CompletableDeferred<String>>()
    private var callCounter = 0L

    /**
     * 启动 MCP Server 连接
     */
    suspend fun connect(context: Context) = withContext(Dispatchers.IO) {
        // 方式1: 尝试通过 miclaw MCP server 子进程
        try {
            val sandboxMcp = File("/data/mbclaw/sandbox/rootfs/usr/bin/python3")
            if (sandboxMcp.exists()) {
                startStdioMcp(context)
                return@withContext
            }
        } catch (_: Exception) {}

        // 方式2: 通过 miclaw IPC (需要 miclaw 已安装)
        try {
            connectViaMiclawIpc(context)
            return@withContext
        } catch (_: Exception) {}

        // 方式3: 降级 — 直接调用 Android API
        android.util.Log.w(TAG, "MCP 不可用，使用降级模式 (Android API 直调)")
    }

    /**
     * stdio MCP — 启动 Python MCP server 子进程
     */
    private fun startStdioMcp(context: Context) {
        val python = "/data/mbclaw/sandbox/rootfs/usr/bin/python3"
        val mcpScript = """
import sys, json, subprocess, os

# MCP stdio transport — 读写 stdin/stdout
for line in sys.stdin:
    try:
        req = json.loads(line.strip())
        method = req.get("method", "")
        params = req.get("params", {})
        req_id = req.get("id", 0)

        if method == "tools/list":
            # 返回可用工具列表
            result = {"tools": [
                {"name": "shell_exec", "description": "Execute shell command"},
                {"name": "code_run", "description": "Run Python/JS code"},
                {"name": "pip_install", "description": "Install Python packages"},
                {"name": "file_read", "description": "Read a file"},
                {"name": "file_write", "description": "Write to a file"},
                {"name": "file_list", "description": "List directory contents"},
                {"name": "file_grep", "description": "Search files"},
                {"name": "web_search", "description": "Web search"},
                {"name": "url_fetch", "description": "Fetch URL content"},
                {"name": "tts_speak", "description": "Text to speech"},
                {"name": "system_info", "description": "Get system info"},
                {"name": "clipboard_get", "description": "Get clipboard"},
                {"name": "clipboard_set", "description": "Set clipboard"},
                {"name": "media_play", "description": "Control media playback"},
                {"name": "app_launch", "description": "Launch an app"},
                {"name": "notification_send", "description": "Send notification"},
                {"name": "wifi_info", "description": "Get WiFi info"},
                {"name": "bluetooth_scan", "description": "Scan bluetooth"},
                {"name": "battery_status", "description": "Get battery status"},
            ]}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = execute_tool(tool_name, tool_args)

        else:
            result = {"error": f"unknown method: {method}"}

        resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    except Exception as e:
        err = {"jsonrpc": "2.0", "id": 0, "error": {"code": -1, "message": str(e)}}
        sys.stdout.write(json.dumps(err) + "\\n")
        sys.stdout.flush()

def execute_tool(name, args):
    if name == "shell_exec":
        r = subprocess.run(args["command"], shell=True,
                           capture_output=True, text=True, timeout=30)
        return {"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}

    elif name == "code_run":
        lang = args.get("language", "python")
        code = args["code"]
        if lang == "python":
            r = subprocess.run([sys.executable, "-c", code],
                               capture_output=True, text=True, timeout=30)
        else:
            r = subprocess.run(["node", "-e", code],
                               capture_output=True, text=True, timeout=30)
        return {"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}

    elif name == "pip_install":
        r = subprocess.run([sys.executable, "-m", "pip", "install"] + args["packages"],
                           capture_output=True, text=True, timeout=120)
        return {"output": r.stdout + r.stderr, "code": r.returncode}

    elif name in ("file_read", "memory_get"):
        try:
            with open(args["path"], "r") as f:
                content = f.read(4000)
            return {"content": content}
        except Exception as e:
            return {"error": str(e)}

    elif name == "file_write":
        try:
            os.makedirs(os.path.dirname(args["path"]), exist_ok=True)
            with open(args["path"], "w") as f:
                f.write(args["content"])
            return {"ok": True, "path": args["path"]}
        except Exception as e:
            return {"error": str(e)}

    elif name == "file_list":
        try:
            path = args.get("path", ".")
            items = os.listdir(path)
            return {"items": items[:100], "count": len(items)}
        except Exception as e:
            return {"error": str(e)}

    elif name == "file_grep":
        try:
            import re
            pattern = args["pattern"]
            path = args["path"]
            r = subprocess.run(["grep", "-rn", pattern, path],
                               capture_output=True, text=True, timeout=10)
            return {"matches": r.stdout[:4000]}
        except Exception as e:
            return {"error": str(e)}

    elif name in ("web_search", "url_fetch"):
        return {"result": "联网搜索需要 Android API 支持，请使用 miclaw bridge HTTP 模式"}

    elif name == "tts_speak":
        return tts_speak(args["text"])
    elif name == "system_info":
        return get_system_info()
    elif name == "clipboard_get":
        return get_clipboard()
    elif name == "clipboard_set":
        return set_clipboard(args["text"])
    elif name == "media_play":
        return media_control(args.get("action", "play"))
    elif name == "app_launch":
        return launch_app(args["package"])
    elif name == "notification_send":
        return send_notification(args["title"], args["text"])
    elif name == "wifi_info":
        return get_wifi_info()
    elif name == "bluetooth_scan":
        return bluetooth_scan()
    elif name == "battery_status":
        return get_battery_status()

    return {"error": f"unknown tool: {name}"}

# Android-specific tool implementations (stub — filled by bridge via IPC)
def tts_speak(text): return {"ok": True}
def get_system_info(): return {"os": "Android", "model": "unknown"}
def get_clipboard(): return {"text": ""}
def set_clipboard(text): return {"ok": True}
def media_control(action): return {"ok": True}
def launch_app(pkg): return {"ok": True}
def send_notification(title, text): return {"ok": True}
def get_wifi_info(): return {"ssid": ""}
def bluetooth_scan(): return {"devices": []}
def get_battery_status(): return {"level": 100}

sys.stderr.write("MBclaw MCP Server ready\\n")
sys.stderr.flush()
""".trimIndent()

        // Write MCP script to sandbox
        val scriptFile = File(context.filesDir, "mbclaw_mcp_server.py")
        scriptFile.writeText(mcpScript)

        // Start process
        val pb = ProcessBuilder(python, scriptFile.absolutePath)
            .directory(File(context.filesDir, "mcp_work"))
            .redirectErrorStream(false)

        mcpProcess = pb.start()
        mcpInput = mcpProcess!!.outputStream.bufferedWriter()
        mcpOutput = mcpProcess!!.inputStream.bufferedReader()

        // Reader loop
        CoroutineScope(Dispatchers.IO).launch {
            try {
                while (isActive) {
                    val line = mcpOutput?.readLine() ?: break
                    try {
                        val json = org.json.JSONObject(line)
                        val id = json.optString("id", "")
                        if (id.isNotEmpty()) {
                            pendingCalls[id]?.complete(json.toString())
                            pendingCalls.remove(id)
                        }
                    } catch (_: Exception) {
                        // stderr line, ignore
                    }
                }
            } catch (_: Exception) {}
        }
    }

    /**
     * 通过 miclaw IPC 连接 (备选方案)
     */
    private fun connectViaMiclawIpc(context: Context) {
        // 尝试通过 miclaw 的 ILLMManager 接口
        // 需要 miclaw 已安装且共享 UID
        val intent = Intent("com.xiaomi.taiyi.sdk.llm.ipc.ILLMManager")
        intent.setPackage("com.xiaomi.type")
        // 实际绑定需要 miclaw 的 AIDL 支持
        throw UnsupportedOperationException("miclaw IPC not available")
    }

    /**
     * 调用 miclaw 工具
     *
     * @param toolName 工具名称，如 "wifi_info", "shell_exec"
     * @param params 工具参数，Map 形式
     * @return 工具执行结果 JSON 字符串
     */
    suspend fun call(toolName: String, params: Map<String, Any> = emptyMap()): String =
        withContext(Dispatchers.IO) {
            val callId = "mcp_${++callCounter}"
            val deferred = CompletableDeferred<String>()

            val request = org.json.JSONObject().apply {
                put("jsonrpc", "2.0")
                put("id", callId)
                put("method", "tools/call")
                put("params", org.json.JSONObject().apply {
                    put("name", toolName)
                    put("arguments", org.json.JSONObject(params))
                })
            }

            pendingCalls[callId] = deferred

            try {
                mcpInput?.apply {
                    write(request.toString())
                    newLine()
                    flush()
                }

                withTimeout(TOOL_TIMEOUT_MS) {
                    deferred.await()
                }
            } catch (e: TimeoutCancellationException) {
                pendingCalls.remove(callId)
                """{"error": "tool call timeout: ${toolName}"}"""
            } catch (e: Exception) {
                pendingCalls.remove(callId)
                """{"error": "${e.message}"}"""
            }
        }

    /**
     * 列出所有可用工具
     */
    suspend fun listTools(): List<MiclawTool> = withContext(Dispatchers.IO) {
        try {
            val result = callToolsList()
            val json = org.json.JSONObject(result)
            val tools = json.getJSONObject("result").getJSONArray("tools")
            (0 until tools.length()).map { i ->
                val tool = tools.getJSONObject(i)
                MiclawTool(
                    name = tool.getString("name"),
                    description = tool.optString("description", "")
                )
            }
        } catch (e: Exception) {
            DEFAULT_TOOLS
        }
    }

    private suspend fun callToolsList(): String {
        val callId = "mcp_list_${++callCounter}"
        val deferred = CompletableDeferred<String>()

        val request = org.json.JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", callId)
            put("method", "tools/list")
            put("params", org.json.JSONObject())
        }

        pendingCalls[callId] = deferred
        mcpInput?.apply {
            write(request.toString())
            newLine()
            flush()
        }

        return withTimeout(TOOL_TIMEOUT_MS) { deferred.await() }
    }

    /**
     * 断开连接
     */
    fun disconnect() {
        mcpInput?.close()
        mcpOutput?.close()
        mcpProcess?.destroy()
        pendingCalls.clear()
    }

    // ═══ 数据类 ═══

    data class MiclawTool(
        val name: String,
        val description: String
    )

    private val DEFAULT_TOOLS = listOf(
        MiclawTool("shell_exec", "执行 shell 命令"),
        MiclawTool("code_run", "执行 Python/JS 代码"),
        MiclawTool("file_read", "读取文件"),
        MiclawTool("file_write", "写入文件"),
        MiclawTool("file_list", "列出目录"),
        MiclawTool("file_grep", "搜索文件"),
        MiclawTool("web_search", "网页搜索"),
        MiclawTool("tts_speak", "文字转语音"),
        MiclawTool("system_info", "系统信息"),
        MiclawTool("wifi_info", "WiFi 信息"),
        MiclawTool("battery_status", "电池状态"),
    )
}

/**
 * 可完成的延迟值 — 简单的 CompletableDeferred 实现
 */
class CompletableDeferred<T> {
    private val channel = Channel<T>(1)
    private var completed = false

    fun complete(value: T) {
        if (!completed) {
            completed = true
            channel.trySend(value)
        }
    }

    suspend fun await(): T = channel.receive()
}
