package org.amnezia.awg.xingsui

import android.content.Context
import android.util.Log
import java.io.File
import java.time.Instant

object XingsuiCrashReporter {
    private const val TAG = "XingsuiCrashReporter"
    private const val FILE_NAME = "xingsui-crash.log"
    private const val MAX_BYTES = 512 * 1024

    @Volatile
    private var appContext: Context? = null

    fun install(context: Context) {
        appContext = context.applicationContext
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            recordException("uncaught:${thread.name}", throwable)
            previous?.uncaughtException(thread, throwable)
        }
        recordEvent("startup", "crash reporter installed")
    }

    fun recordEvent(source: String, message: String) {
        Log.i(TAG, "$source: $message")
        append("$source: $message")
    }

    fun recordException(source: String, throwable: Throwable) {
        Log.e(TAG, source, throwable)
        append("$source: ${Log.getStackTraceString(throwable)}")
    }

    private fun append(message: String) {
        val context = appContext ?: return
        runCatching {
            val file = File(context.filesDir, FILE_NAME)
            if (file.length() > MAX_BYTES) {
                file.writeText("")
            }
            file.appendText("${Instant.now()} $message\n")
        }.onFailure {
            Log.e(TAG, "Failed to write local crash log", it)
        }
    }
}
