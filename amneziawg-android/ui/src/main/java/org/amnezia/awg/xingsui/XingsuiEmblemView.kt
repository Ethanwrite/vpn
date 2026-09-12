package org.amnezia.awg.xingsui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.provider.Settings
import androidx.core.graphics.PathParser

/** Flat, transparent emblem. Contours originate in design/emblem.json. */
class XingsuiEmblemView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null, defStyleAttr: Int = 0) : View(context, attrs, defStyleAttr) {
    enum class Phase { IDLE, CONNECTING, CONNECTED, LOST }
    private var phase = Phase.IDLE
    private var assembly = 0f
    private var opacity = 1f
    private var movement: ValueAnimator? = null
    private var loading: ValueAnimator? = null
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 4.5f
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
        color = 0xFF922D28.toInt()
    }
    private val sickle = listOf(SICKLE).map { requireNotNull(PathParser.createPathFromPathData(it)) }
    private val hammer = listOf(SHAFT, HEAD).map { requireNotNull(PathParser.createPathFromPathData(it)) }
    fun currentPhase(): Phase = phase
    private fun motionEnabled() = Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) > 0f
    fun setPhase(next: Phase, animate: Boolean = true) {
        if (phase == next) return
        phase = next
        movement?.cancel()
        loading?.cancel()
        opacity = 1f
        val target = if (next == Phase.CONNECTING || next == Phase.CONNECTED) 1f else 0f
        if (animate && motionEnabled() && isShown) {
            movement = ValueAnimator.ofFloat(assembly, target).apply {
                duration = 650
                interpolator = AccelerateDecelerateInterpolator()
                addUpdateListener { assembly = it.animatedValue as Float; invalidate() }
                start()
            }
            startLoading()
        } else assembly = target
        invalidate()
    }
    private fun startLoading() {
        if (phase != Phase.CONNECTING || !motionEnabled() || !isShown) return
        loading?.cancel()
        loading = ValueAnimator.ofFloat(1f, .45f).apply {
            duration = 700
            repeatCount = ValueAnimator.INFINITE
            repeatMode = ValueAnimator.REVERSE
            addUpdateListener { opacity = it.animatedValue as Float; invalidate() }
            start()
        }
    }
    override fun onWindowVisibilityChanged(visibility: Int) {
        super.onWindowVisibilityChanged(visibility)
        if (visibility == VISIBLE) startLoading() else { movement?.cancel(); loading?.cancel() }
    }
    override fun onAttachedToWindow() { super.onAttachedToWindow(); startLoading() }
    override fun onDetachedFromWindow() { movement?.cancel(); loading?.cancel(); super.onDetachedFromWindow() }
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val size = minOf(width, height).toFloat()
        if (size <= 0f) return
        canvas.save()
        canvas.translate((width-size)/2f, (height-size)/2f)
        canvas.scale(size/200f, size/200f)
        paint.alpha = (255 * opacity).toInt()
        val split = 1f-assembly
        canvas.save()
        val hammerMask = android.graphics.Path()
        val transform = android.graphics.Matrix().apply { setTranslate(-7f*split, -5f*split) }
        hammer.forEach { path ->
            val expanded = android.graphics.Path()
            Paint(paint).apply { style = Paint.Style.FILL_AND_STROKE }.getFillPath(path, expanded)
            expanded.transform(transform)
            hammerMask.addPath(expanded)
        }
        @Suppress("DEPRECATION")
        canvas.clipPath(hammerMask, android.graphics.Region.Op.DIFFERENCE)
        canvas.translate(5f*split, 4f*split)
        sickle.forEach { canvas.drawPath(it, paint) }
        canvas.restore()
        canvas.translate(-7f*split, -5f*split)
        hammer.forEach { canvas.drawPath(it, paint) }
        canvas.restore()
    }
    private companion object {
        const val SICKLE = "M116 24C159 43 181 78 174 115C168 149 143 172 109 174C86 176 64 168 49 155L30 175Q23 182 18 175Q14 170 21 163L39 144Q37 137 43 136L49 131Q52 129 56 134C77 155 109 160 137 143C158 130 165 107 158 82C152 59 137 40 116 24Z"
        const val SHAFT = "M72 82L157 172Q164 179 171 172Q178 165 169 157L84 70Z"
        const val HEAD = "M38 79L76 41L101 45Q106 46 102 51L55 99Q52 102 49 99L37 87Q34 84 38 79Z"
    }
}
