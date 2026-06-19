package com.mbclaw.config

/**
 * MBclaw 全局配置
 *
 * 优先级: 用户设置 > miclaw beta key > 内建默认值 > 免费降级
 */
object MBclawConfig {

    // ═══ LLM 配置 ═══

    /** LLM 模式 */
    enum class LLMMode {
        /** miclaw 内测 API (api.mify.mioffice.cn) */
        MICLAW_BETA,
        /** 自建 MBclaw 云端服务器 */
        MBCLAW_CLOUD,
        /** 本地 MBclaw-Lite API (本机 Python) */
        MBCLAW_LOCAL,
        /** 免费模式 — DeepSeek 免费 API */
        FREE_DEEPSEEK,
        /** 完全离线 — 本地小模型 */
        OFFLINE
    }

    var llmMode: LLMMode = LLMMode.MBCLAW_LOCAL

    /** miclaw 内测 API Key */
    var miclawBetaKey: String? = null

    /** 自建云端服务器地址 */
    var cloudHost: String = ""
    var cloudPort: Int = 18789

    /** 本地 API 端口 */
    var localApiPort: Int = 18790

    /** DeepSeek 免费代理端口 */
    var deepseekProxyPort: Int = 8899

    // ═══ 语音配置 ═══

    /** 唤醒词 (默认保持"小爱同学"兼容 AIVSE SDK) */
    var wakeWord: String = "小爱同学"

    /** 静音检测超时 (秒)，超时自动发送 */
    var silenceTimeoutSec: Float = 5.5f

    /** 连续对话模式 */
    var continuousConversation: Boolean = true

    /** TTS 引擎 */
    var ttsEngine: String = "com.xiaomi.mibrain.speech"

    // ═══ 沙箱配置 ═══

    /** 是否启用本地 Linux 沙箱 */
    var sandboxEnabled: Boolean = true

    /** proot rootfs 路径 */
    var sandboxRootfs: String = "/data/mbclaw/sandbox/rootfs"

    /** 沙箱内存限制 (MB) */
    var sandboxMaxMemoryMb: Int = 512

    /** 沙箱 CPU 限制 (核心数) */
    var sandboxMaxCpus: Int = 2

    // ═══ 云端链路配置 ═══

    /** 是否启用云端隧道 */
    var cloudTunnelEnabled: Boolean = false

    /** 隧道类型 */
    enum class TunnelType {
        CLOUDFLARE,  // Cloudflare Tunnel (推荐)
        FRP,         // frp 内网穿透
        DIRECT       // 直连 (公网IP)
    }
    var tunnelType: TunnelType = TunnelType.CLOUDFLARE

    /** Cloudflare Tunnel Token */
    var cloudflareToken: String = ""

    // ═══ 从 SharedPreferences 加载 ═══

    fun load(prefs: android.content.SharedPreferences) {
        llmMode = LLMMode.valueOf(
            prefs.getString("llm_mode", LLMMode.MBCLAW_LOCAL.name)!!
        )
        miclawBetaKey = prefs.getString("miclaw_beta_key", null)
        cloudHost = prefs.getString("cloud_host", "") ?: ""
        cloudPort = prefs.getInt("cloud_port", 18789)
        localApiPort = prefs.getInt("local_api_port", 18790)
        deepseekProxyPort = prefs.getInt("deepseek_proxy_port", 8899)

        wakeWord = prefs.getString("wake_word", "小爱同学") ?: "小爱同学"
        silenceTimeoutSec = prefs.getFloat("silence_timeout", 5.5f)
        continuousConversation = prefs.getBoolean("continuous_conversation", true)
        ttsEngine = prefs.getString("tts_engine", "com.xiaomi.mibrain.speech")!!

        sandboxEnabled = prefs.getBoolean("sandbox_enabled", true)
        sandboxRootfs = prefs.getString("sandbox_rootfs", "/data/mbclaw/sandbox/rootfs")!!

        cloudTunnelEnabled = prefs.getBoolean("cloud_tunnel_enabled", false)
        tunnelType = TunnelType.valueOf(
            prefs.getString("tunnel_type", TunnelType.CLOUDFLARE.name)!!
        )
        cloudflareToken = prefs.getString("cloudflare_token", "") ?: ""
    }

    fun save(prefs: android.content.SharedPreferences) {
        prefs.edit().apply {
            putString("llm_mode", llmMode.name)
            putString("miclaw_beta_key", miclawBetaKey)
            putString("cloud_host", cloudHost)
            putInt("cloud_port", cloudPort)
            putInt("local_api_port", localApiPort)
            putInt("deepseek_proxy_port", deepseekProxyPort)
            putString("wake_word", wakeWord)
            putFloat("silence_timeout", silenceTimeoutSec)
            putBoolean("continuous_conversation", continuousConversation)
            putString("tts_engine", ttsEngine)
            putBoolean("sandbox_enabled", sandboxEnabled)
            putString("sandbox_rootfs", sandboxRootfs)
            putBoolean("cloud_tunnel_enabled", cloudTunnelEnabled)
            putString("tunnel_type", tunnelType.name)
            putString("cloudflare_token", cloudflareToken)
            apply()
        }
    }

    /** 获取当前活跃的 LLM 端点 */
    fun resolveEndpoint(): String {
        return when (llmMode) {
            LLMMode.MICLAW_BETA -> {
                val key = miclawBetaKey ?: throw IllegalStateException("miclaw beta key not set")
                "https://api.mify.mioffice.cn/v1"
            }
            LLMMode.MBCLAW_CLOUD -> {
                if (cloudHost.isBlank()) throw IllegalStateException("cloud host not set")
                "https://${cloudHost}:${cloudPort}/v1"
            }
            LLMMode.MBCLAW_LOCAL -> "http://127.0.0.1:${localApiPort}/v1"
            LLMMode.FREE_DEEPSEEK -> "http://127.0.0.1:${deepseekProxyPort}/v1"
            LLMMode.OFFLINE -> "http://127.0.0.1:${localApiPort}/v1"  // fallback to local
        }
    }
}
