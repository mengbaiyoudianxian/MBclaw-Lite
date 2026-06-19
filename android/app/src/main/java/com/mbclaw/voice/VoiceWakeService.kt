package com.mbclaw.voice

import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.*
import java.io.File
import java.io.FileOutputStream

/**
 * Voice Wake Service — 语音系统 (AIVSE 劫持 + VAD + 连续对话)
 *
 * 架构:
 *   1. AIVSE SDK 检测到唤醒词 (默认"小爱同学")
 *   2. MBclaw 劫持唤醒事件 — 不发往小米服务
 *   3. 开始录音 + VAD (Voice Activity Detection) 实时检测
 *   4. 5-6 秒静音 → 自动断句 → STT 转文字 → MBclaw Agent
 *   5. Agent 处理 → TTS 语音回复 → 继续监听
 *
 * AIVSE 劫持策略:
 *   - 方案A (推荐): 监听系统广播 + 拦截 intent
 *   - 方案B: AccessibilityService 监听语音助手触发
 *   - 方案C: 替换系统语音助手默认应用
 *
 * 离线处理:
 *   - VAD: WebRTC VAD (C++ 库, ~1MB)
 *   - STT: 优先使用系统 SpeechRecognizer (在线)，备选 Vosk (离线)
 *   - TTS: 系统 TextToSpeech 引擎
 */
class VoiceWakeService : Service() {

    companion object {
        private const val TAG = "MBclaw-Voice"

        // VAD 配置
        private const val SAMPLE_RATE = 16000
        private const val FRAME_SIZE_MS = 30
        private const val FRAME_SIZE_BYTES = SAMPLE_RATE * FRAME_SIZE_MS / 1000 * 2  // 16-bit mono

        // 静音检测 — 连续静音帧数阈值
        private const val SILENCE_FRAMES_THRESHOLD = 180  // ~5.4 秒 @ 30ms/frame

        // 录音缓冲区
        private const val AUDIO_BUFFER_SIZE = FRAME_SIZE_BYTES * 4
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mainHandler = Handler(Looper.getMainLooper())

    // 状态
    private var isListening = false
    private var isRecording = false
    private var silenceFrameCount = 0
    private var conversationActive = false

    // 录音
    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null

    // 回调
    var onWakeWordDetected: (() -> Unit)? = null
    var onUtteranceComplete: ((audioFile: File) -> Unit)? = null
    var onSpeechResult: ((text: String) -> Unit)? = null
    var onError: ((error: String) -> Unit)? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "VoiceWakeService started")
        startWakeWordDetection()
        return START_STICKY
    }

    // ═══════════════════════════════════════════════════
    // 唤醒词检测
    // ═══════════════════════════════════════════════════

    /**
     * 启动唤醒词监听
     *
     * 方案: 使用系统 SpeechRecognizer 持续监听 + 关键词过滤
     * AIVSE SDK 在 HyperOS 中负责硬件级唤醒，这里做应用层兜底
     */
    private fun startWakeWordDetection() {
        // 实际集成 AIVSE SDK 需要:
        //   1. 引入 com.xiaomi.aivse SDK
        //   2. 注册 WakeUpEngine.WakeUpCallback
        //   3. 在回调中触发 onWakeWordDetected?.invoke()
        //
        // 伪代码:
        //   AIVSE.getInstance().setWakeUpCallback { wakeWord ->
        //       Log.i(TAG, "Wake word detected: $wakeWord")
        //       onWakeWordDetected?.invoke()
        //       startContinuousListening()
        //   }

        // 降级方案: 使用 Android SpeechRecognizer
        Log.i(TAG, "Waiting for wake word...")
    }

    // ═══════════════════════════════════════════════════
    // 连续对话录音 + VAD
    // ═══════════════════════════════════════════════════

    /**
     * 开始连续对话录音
     */
    fun startContinuousListening() {
        if (isListening) return
        isListening = true
        conversationActive = true

        scope.launch {
            startRecording()
            Log.i(TAG, "Continuous listening started")
        }
    }

    /**
     * 开始录音 + VAD
     */
    private suspend fun startRecording() = withContext(Dispatchers.IO) {
        val bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        ).coerceAtLeast(AUDIO_BUFFER_SIZE)

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                onError?.invoke("Failed to initialize audio recorder")
                return@withContext
            }

            audioRecord?.startRecording()
            isRecording = true

            val buffer = ByteArray(FRAME_SIZE_BYTES)
            val utteranceBuffer = mutableListOf<ByteArray>()
            silenceFrameCount = 0
            var currentUtteranceStart = true

            while (isRecording && isActive) {
                val bytesRead = audioRecord?.read(buffer, 0, FRAME_SIZE_BYTES) ?: -1
                if (bytesRead <= 0) continue

                val frame = buffer.copyOf(bytesRead)
                utteranceBuffer.add(frame)

                // VAD — 简单能量检测
                val hasSpeech = detectSpeech(frame)

                if (hasSpeech) {
                    silenceFrameCount = 0
                    currentUtteranceStart = false
                } else {
                    silenceFrameCount++
                }

                // 检测到话语结束 (连续静音超过阈值)
                if (!currentUtteranceStart && silenceFrameCount >= SILENCE_FRAMES_THRESHOLD) {
                    Log.i(TAG, "Utterance complete (silence: ${silenceFrameCount * FRAME_SIZE_MS}ms)")

                    // 保存录音片段
                    val audioFile = saveUtterance(utteranceBuffer)
                    utteranceBuffer.clear()
                    silenceFrameCount = 0
                    currentUtteranceStart = true

                    // 触发 STT
                    onUtteranceComplete?.invoke(audioFile)
                }
            }

        } catch (e: SecurityException) {
            onError?.invoke("录音权限未授予: ${e.message}")
        } catch (e: Exception) {
            onError?.invoke("录音错误: ${e.message}")
        } finally {
            stopRecordingInternal()
        }
    }

    /**
     * 简单语音检测 (RMS 能量)
     *
     * 生产环境替换为 WebRTC VAD (GMM-based, 更准确)
     */
    private fun detectSpeech(frame: ByteArray): Boolean {
        var sum = 0L
        for (i in frame.indices step 2) {
            if (i + 1 < frame.size) {
                // 16-bit PCM little-endian
                val sample = ((frame[i + 1].toInt() shl 8) or (frame[i].toInt() and 0xFF)).toShort()
                sum += (sample * sample).toLong()
            }
        }
        val rms = kotlin.math.sqrt(sum.toDouble() / (frame.size / 2))
        return rms > 500.0  // 阈值可调
    }

    /**
     * 保存录音片段到 WAV 文件
     */
    private fun saveUtterance(frames: List<ByteArray>): File {
        val file = File(cacheDir, "utterance_${System.currentTimeMillis()}.wav")
        FileOutputStream(file).use { fos ->
            // WAV header
            val totalDataLen = frames.sumOf { it.size }
            val header = ByteArray(44)

            // RIFF header
            "RIFF".toByteArray().copyInto(header, 0)
            (36 + totalDataLen).let {
                header[4] = (it and 0xFF).toByte()
                header[5] = (it shr 8 and 0xFF).toByte()
                header[6] = (it shr 16 and 0xFF).toByte()
                header[7] = (it shr 24 and 0xFF).toByte()
            }
            "WAVE".toByteArray().copyInto(header, 8)

            // fmt chunk
            "fmt ".toByteArray().copyInto(header, 12)
            16.let { header[16] = it.toByte() }  // PCM
            1.let { header[20] = it.toByte(); header[21] = 0 }  // format = PCM
            1.let { header[22] = it.toByte(); header[23] = 0 }  // channels = 1
            SAMPLE_RATE.let {
                header[24] = (it and 0xFF).toByte()
                header[25] = (it shr 8 and 0xFF).toByte()
                header[26] = (it shr 16 and 0xFF).toByte()
                header[27] = (it shr 24 and 0xFF).toByte()
            }
            (SAMPLE_RATE * 2).let {  // byte rate
                header[28] = (it and 0xFF).toByte()
                header[29] = (it shr 8 and 0xFF).toByte()
                header[30] = (it shr 16 and 0xFF).toByte()
                header[31] = (it shr 24 and 0xFF).toByte()
            }
            2.let { header[32] = it.toByte(); header[33] = 0 }  // block align
            16.let { header[34] = it.toByte(); header[35] = 0 }  // bits per sample

            // data chunk
            "data".toByteArray().copyInto(header, 36)
            totalDataLen.let {
                header[40] = (it and 0xFF).toByte()
                header[41] = (it shr 8 and 0xFF).toByte()
                header[42] = (it shr 16 and 0xFF).toByte()
                header[43] = (it shr 24 and 0xFF).toByte()
            }

            fos.write(header)
            frames.forEach { fos.write(it) }
        }

        Log.d(TAG, "Saved utterance: ${file.length()} bytes")
        return file
    }

    // ═══════════════════════════════════════════════════
    // 停止
    // ═══════════════════════════════════════════════════

    fun stopListening() {
        isListening = false
        conversationActive = false
        stopRecordingInternal()
    }

    private fun stopRecordingInternal() {
        isRecording = false
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    override fun onDestroy() {
        stopListening()
        scope.cancel()
        super.onDestroy()
    }
}
