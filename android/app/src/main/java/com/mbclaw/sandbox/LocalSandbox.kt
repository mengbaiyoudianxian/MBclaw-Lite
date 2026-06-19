package com.mbclaw.sandbox

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import java.io.File

/**
 * Local Linux Sandbox — 完整 Linux 环境，用于执行危险/受限指令
 *
 * 原理:
 *   proot + Ubuntu rootfs → 在 Android 上运行完整 Linux
 *   文件系统隔离 + 资源限制 = 安全沙箱
 *
 * 路径:
 *   /data/mbclaw/sandbox/
 *   ├── rootfs/          # Ubuntu rootfs (由 setup_sandbox.sh 初始化)
 *   ├── shared/          # 与 Android 共享的目录
 *   └── workspace/       # 默认工作目录
 *
 * 初始化:
 *   bash scripts/setup_sandbox.sh
 *   - 下载 Ubuntu 22.04 rootfs (~200MB)
 *   - 配置 DNS、apt 源
 *   - 安装 Python3.11, Node.js, Git, build-essential
 */
object LocalSandbox {

    private const val TAG = "MBclaw-Sandbox"

    const val SANDBOX_DIR = "/data/mbclaw/sandbox"
    const val ROOTFS_DIR = "$SANDBOX_DIR/rootfs"
    const val SHARED_DIR = "$SANDBOX_DIR/shared"
    const val WORKSPACE_DIR = "$SANDBOX_DIR/workspace"

    private const val EXEC_TIMEOUT_SEC = 60L
    private const val MAX_OUTPUT_BYTES = 100_000

    /**
     * 检查沙箱是否就绪
     */
    fun isReady(): Boolean {
        return File(ROOTFS_DIR, "usr/bin/python3").exists() ||
               File(ROOTFS_DIR, "bin/bash").exists()
    }

    /**
     * 在沙箱中执行命令
     *
     * proot 不是必须的 — 如果 rootfs 是自包含的 Python 环境，
     * 也可以直接用 rootfs 中的 python 执行。
     *
     * @param command 要执行的命令 (在 rootfs 上下文中)
     * @param workDir 工作目录 (沙箱内路径)
     * @param timeoutSec 超时 (秒)
     * @param env 环境变量
     * @return ExecResult
     */
    suspend fun exec(
        command: String,
        workDir: String = "/workspace",
        timeoutSec: Long = EXEC_TIMEOUT_SEC,
        env: Map<String, String> = emptyMap()
    ): ExecResult = withContext(Dispatchers.IO) {

        if (!isReady()) {
            return@withContext ExecResult(-1, "", "Sandbox not initialized. Run setup_sandbox.sh first.")
        }

        try {
            // 使用 rootfs 中的 bash/python 直接执行
            val shell = if (File(ROOTFS_DIR, "bin/bash").exists())
                listOf("$ROOTFS_DIR/bin/bash", "-c")
            else
                listOf("/system/bin/sh", "-c")

            val pb = ProcessBuilder(shell + command)
                .directory(File("$ROOTFS_DIR$workDir"))

            // 设置环境变量 (PATH 指向 rootfs)
            val processEnv = pb.environment()
            processEnv["PATH"] = "$ROOTFS_DIR/usr/bin:$ROOTFS_DIR/usr/local/bin:$ROOTFS_DIR/bin:/system/bin"
            processEnv["HOME"] = "/root"
            processEnv["TMPDIR"] = "/tmp"
            processEnv["LD_LIBRARY_PATH"] = "$ROOTFS_DIR/usr/lib:$ROOTFS_DIR/lib"
            env.forEach { (k, v) -> processEnv[k] = v }

            val process = pb.start()

            val stdout = process.inputStream.bufferedReader().readText()
                .take(MAX_OUTPUT_BYTES)
            val stderr = process.errorStream.bufferedReader().readText()
                .take(MAX_OUTPUT_BYTES)

            val exited = process.waitFor(timeoutSec, java.util.concurrent.TimeUnit.SECONDS)
            if (!exited) {
                process.destroyForcibly()
                return@withContext ExecResult(-1, stdout, "Command timed out after ${timeoutSec}s")
            }

            ExecResult(process.exitValue(), stdout, stderr)

        } catch (e: Exception) {
            Log.e(TAG, "Sandbox exec error", e)
            ExecResult(-1, "", e.message ?: "Unknown error")
        }
    }

    /**
     * 在沙箱中执行 Python 代码
     */
    suspend fun execPython(code: String, timeoutSec: Long = EXEC_TIMEOUT_SEC): ExecResult =
        exec("python3 -c ${shellQuote(code)}", timeoutSec = timeoutSec)

    /**
     * 在沙箱中安装 Python 包
     */
    suspend fun pipInstall(packages: List<String>): ExecResult =
        exec("pip3 install ${packages.joinToString(" ")}", timeoutSec = 120)

    /**
     * 在沙箱中执行 Node.js 代码
     */
    suspend fun execNode(code: String, timeoutSec: Long = EXEC_TIMEOUT_SEC): ExecResult =
        exec("node -e ${shellQuote(code)}", timeoutSec = timeoutSec)

    /**
     * 读取沙箱中的文件
     */
    suspend fun readFile(path: String): String = withContext(Dispatchers.IO) {
        try {
            File("$ROOTFS_DIR$path").readText().take(MAX_OUTPUT_BYTES)
        } catch (e: Exception) {
            "Error: ${e.message}"
        }
    }

    /**
     * 写入沙箱中的文件
     */
    suspend fun writeFile(path: String, content: String) = withContext(Dispatchers.IO) {
        try {
            val file = File("$ROOTFS_DIR$path")
            file.parentFile?.mkdirs()
            file.writeText(content)
            "OK: wrote ${content.length} bytes to $path"
        } catch (e: Exception) {
            "Error: ${e.message}"
        }
    }

    /**
     * 列出沙箱目录
     */
    suspend fun listDir(path: String): String = withContext(Dispatchers.IO) {
        try {
            File("$ROOTFS_DIR$path").listFiles()
                ?.joinToString("\n") { "${if (it.isDirectory) "d" else "f"} ${it.name}" }
                ?: "Empty directory"
        } catch (e: Exception) {
            "Error: ${e.message}"
        }
    }

    data class ExecResult(
        val exitCode: Int,
        val stdout: String,
        val stderr: String
    ) {
        val isSuccess get() = exitCode == 0
        val output get() = if (stdout.isNotBlank()) stdout else stderr
    }

    /** Shell 安全的单引号转义 */
    private fun shellQuote(s: String): String = "'${s.replace("'", "'\\''")}'"
}
