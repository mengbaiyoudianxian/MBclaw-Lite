package com.mbclaw

import android.app.Application
import android.content.Intent
import android.content.SharedPreferences
import android.util.Log
import com.mbclaw.agent.AgentRuntimeService
import com.mbclaw.config.MBclawConfig
import com.mbclaw.voice.VoiceWakeService

/**
 * MBclaw Application — 全局初始化
 */
class MBclawApplication : Application() {

    companion object {
        private const val TAG = "MBclaw-App"
        lateinit var instance: MBclawApplication
            private set
    }

    lateinit var prefs: SharedPreferences
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this

        // 初始化配置
        prefs = getSharedPreferences("mbclaw_config", MODE_PRIVATE)
        MBclawConfig.load(prefs)

        Log.i(TAG, "MBclaw starting — LLM mode: ${MBclawConfig.llmMode}")

        // 启动核心服务
        startCoreServices()
    }

    private fun startCoreServices() {
        // Agent Runtime — 必须先启动
        startService(Intent(this, AgentRuntimeService::class.java))

        // 语音唤醒
        startService(Intent(this, VoiceWakeService::class.java))

        // 云端连接 (按需)
        if (MBclawConfig.cloudTunnelEnabled) {
            startService(Intent(this, com.mbclaw.cloud.CloudConnectorService::class.java))
        }
    }
}
