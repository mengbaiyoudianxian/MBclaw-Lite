package com.mbclaw.config

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * 开机自启动接收器
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "MBclaw-Boot"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Log.i(TAG, "Boot completed — starting MBclaw services")
            // Application.onCreate 会自动启动所有服务
        }
    }
}
