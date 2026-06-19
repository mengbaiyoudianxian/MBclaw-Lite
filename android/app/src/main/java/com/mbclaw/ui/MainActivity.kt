package com.mbclaw.ui

import android.os.Bundle
import android.view.View
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.mbclaw.MBclawApplication
import com.mbclaw.agent.AgentRuntimeService
import com.mbclaw.config.MBclawConfig
import com.mbclaw.voice.VoiceWakeService
import kotlinx.coroutines.launch

/**
 * MainActivity — MBclaw 主界面
 *
 * 保留约 70% miclaw UI:
 *   ✅ 对话气泡列表
 *   ✅ 底部输入栏 (输入框 + 发送按钮 + 语音按钮)
 *   ✅ 顶部标题栏
 *   ✅ 暗色/亮色主题
 *
 * 替换约 30%:
 *   🔄 MBclaw 品牌 (Logo、配色、名称)
 *   🔄 网关状态指示器
 *   🔄 记忆/技能面板入口
 *   🔄 沙箱终端入口
 *   🔄 云端状态指示器
 */
class MainActivity : AppCompatActivity() {

    private lateinit var chatRecyclerView: RecyclerView
    private lateinit var inputEditText: EditText
    private lateinit var sendButton: ImageButton
    private lateinit var voiceButton: ImageButton
    private lateinit var titleTextView: TextView
    private lateinit var gatewayStatusView: View
    private lateinit var cloudStatusView: View

    private val chatAdapter = ChatAdapter()
    private var agentService: AgentRuntimeService? = null
    private var voiceService: VoiceWakeService? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // 绑定视图
        chatRecyclerView = findViewById(R.id.chat_recycler)
        inputEditText = findViewById(R.id.input_text)
        sendButton = findViewById(R.id.send_button)
        voiceButton = findViewById(R.id.voice_button)
        titleTextView = findViewById(R.id.title_text)
        gatewayStatusView = findViewById(R.id.gateway_status)
        cloudStatusView = findViewById(R.id.cloud_status)

        // 初始化聊天列表
        chatRecyclerView.layoutManager = LinearLayoutManager(this)
        chatRecyclerView.adapter = chatAdapter
        chatRecyclerView.setHasFixedSize(true)

        // 标题栏 — MBclaw 品牌
        titleTextView.text = "MBclaw"

        // 状态指示器
        updateStatusIndicators()

        // 发送按钮
        sendButton.setOnClickListener { sendMessage() }

        // 语音按钮 (长按录音)
        voiceButton.setOnLongClickListener {
            startVoiceInput()
            true
        }
        voiceButton.setOnClickListener {
            // 短按: 切换连续对话模式
            toggleContinuousConversation()
        }

        // 绑定服务回调
        setupServiceCallbacks()

        // 欢迎消息
        addMessage(ChatMessage(
            role = "assistant",
            content = "你好！我是 **MBclaw**\n\n" +
                "运行在你的 Android 设备上，拥有 miclaw 的全部工具能力。\n" +
                "WiFi 管理 · 蓝牙 · 短信 · 相机 · 文件 · 日历 · 笔记 · 闹钟 · 搜索 · 代码执行\n\n" +
                "直接告诉我想做什么吧！",
            timestamp = System.currentTimeMillis()
        ))
    }

    /**
     * 发送文字消息
     */
    private fun sendMessage() {
        val text = inputEditText.text.toString().trim()
        if (text.isEmpty()) return

        // 清空输入框
        inputEditText.text.clear()

        // 显示用户消息
        addMessage(ChatMessage(
            role = "user",
            content = text,
            timestamp = System.currentTimeMillis()
        ))

        // 显示 "正在思考" 提示
        val thinkingMsg = addMessage(ChatMessage(
            role = "assistant",
            content = "🤔 正在思考...",
            timestamp = System.currentTimeMillis(),
            isThinking = true
        ))

        // 调用 Agent
        lifecycleScope.launch {
            try {
                val response = agentService?.processMessage(text)
                // 移除 "正在思考"
                chatAdapter.removeMessage(thinkingMsg)

                if (response != null) {
                    addMessage(ChatMessage(
                        role = "assistant",
                        content = response,
                        timestamp = System.currentTimeMillis()
                    ))
                }
            } catch (e: Exception) {
                chatAdapter.removeMessage(thinkingMsg)
                addMessage(ChatMessage(
                    role = "assistant",
                    content = "抱歉，处理消息时出错: ${e.message}",
                    timestamp = System.currentTimeMillis(),
                    isError = true
                ))
            }
        }
    }

    /**
     * 语音输入
     */
    private fun startVoiceInput() {
        voiceService?.startContinuousListening()
        Toast.makeText(this, "🎤 正在聆听... (静音 5-6 秒自动发送)", Toast.LENGTH_SHORT).show()
    }

    /**
     * 切换连续对话模式
     */
    private fun toggleContinuousConversation() {
        val config = MBclawConfig
        config.continuousConversation = !config.continuousConversation
        config.save(MBclawApplication.instance.prefs)

        val msg = if (config.continuousConversation)
            "连续对话: 开启 (无需重复唤醒)"
        else
            "连续对话: 关闭"

        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    /**
     * 更新网关状态指示器
     */
    private fun updateStatusIndicators() {
        // 网关状态
        val gatewayOnline = true  // TODO: 检查本地 API 健康
        gatewayStatusView.visibility =
            if (gatewayOnline) View.VISIBLE else View.GONE

        // 云端状态
        val cloudOnline = MBclawConfig.cloudTunnelEnabled
        cloudStatusView.visibility =
            if (cloudOnline) View.VISIBLE else View.GONE
    }

    /**
     * 设置服务回调
     */
    private fun setupServiceCallbacks() {
        // 语音回调
        voiceService?.onUtteranceComplete = { audioFile ->
            runOnUiThread {
                addMessage(ChatMessage(
                    role = "user",
                    content = "🎤 语音输入 (${audioFile.length() / 1024}KB)...",
                    timestamp = System.currentTimeMillis()
                ))
            }
            // TODO: STT 转文字 → 调用 Agent
        }

        voiceService?.onError = { error ->
            runOnUiThread {
                Toast.makeText(this, "语音错误: $error", Toast.LENGTH_SHORT).show()
            }
        }

        // Agent 回调
        agentService?.onAgentThinking = { thinking ->
            runOnUiThread {
                // 可在 UI 上显示思考过程
            }
        }

        agentService?.onToolCall = { toolName, params ->
            runOnUiThread {
                addMessage(ChatMessage(
                    role = "system",
                    content = "🔧 调用工具: $toolName($params)",
                    timestamp = System.currentTimeMillis()
                ))
            }
        }
    }

    /**
     * 添加消息到聊天列表
     */
    private fun addMessage(msg: ChatMessage): ChatMessage {
        chatAdapter.addMessage(msg)
        chatRecyclerView.scrollToPosition(chatAdapter.itemCount - 1)
        return msg
    }
}

/**
 * 聊天消息数据类
 */
data class ChatMessage(
    val role: String,       // "user" | "assistant" | "system"
    val content: String,
    val timestamp: Long,
    val isThinking: Boolean = false,
    val isError: Boolean = false
)

/**
 * 聊天列表适配器 (简化版)
 */
class ChatAdapter : RecyclerView.Adapter<ChatAdapter.ViewHolder>() {

    private val messages = mutableListOf<ChatMessage>()

    fun addMessage(msg: ChatMessage) {
        messages.add(msg)
        notifyItemInserted(messages.size - 1)
    }

    fun removeMessage(msg: ChatMessage) {
        val idx = messages.indexOf(msg)
        if (idx >= 0) {
            messages.removeAt(idx)
            notifyItemRemoved(idx)
        }
    }

    override fun onCreateViewHolder(parent: android.view.ViewGroup, viewType: Int): ViewHolder {
        val view = android.view.LayoutInflater.from(parent.context)
            .inflate(android.R.layout.simple_list_item_2, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val msg = messages[position]
        val prefix = when (msg.role) {
            "user" -> "👤 你"
            "assistant" -> "🤖 MBclaw"
            "system" -> "⚙️ 系统"
            else -> msg.role
        }
        holder.text1.text = prefix
        holder.text2.text = msg.content
    }

    override fun getItemCount() = messages.size

    class ViewHolder(view: android.view.View) : RecyclerView.ViewHolder(view) {
        val text1: TextView = view.findViewById(android.R.id.text1)
        val text2: TextView = view.findViewById(android.R.id.text2)
    }
}
