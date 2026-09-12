package org.amnezia.awg.xingsui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.random.Random

/** Sparse, deterministic paper specks. No bitmap, gradient or animation allocation. */
class XingsuiPaperTextureView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x14282825; strokeCap = Paint.Cap.ROUND }
    private var points = floatArrayOf()
    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        val density = resources.displayMetrics.density
        paint.strokeWidth = .65f * density
        val random = Random(41)
        points = FloatArray((w * h / (density * density * 65)).toInt().coerceAtMost(12000) * 2) { index ->
            random.nextFloat() * if (index % 2 == 0) w else h
        }
    }
    override fun onDraw(canvas: Canvas) { super.onDraw(canvas); canvas.drawPoints(points, paint) }
}
