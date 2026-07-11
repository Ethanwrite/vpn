package org.amnezia.awg.xingsui

import java.util.Locale

/** 免费流量展示格式化工具：把字节数转成用户可读的 MB / GB 文案。 */
object XingsuiTraffic {
    fun formatBytes(bytes: Long): String {
        val safe = bytes.coerceAtLeast(0L)
        val mb = safe.toDouble() / (1024.0 * 1024.0)
        return if (mb >= 1024.0) {
            trimZero(mb / 1024.0) + "GB"
        } else {
            trimZero(mb) + "MB"
        }
    }

    private fun trimZero(value: Double): String {
        val rounded = String.format(Locale.US, "%.1f", value)
        return if (rounded.endsWith(".0")) rounded.dropLast(2) else rounded
    }
}
