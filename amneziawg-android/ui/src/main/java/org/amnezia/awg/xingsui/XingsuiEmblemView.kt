package org.amnezia.awg.xingsui

import android.animation.TimeInterpolator
import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PathEffect
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.DecelerateInterpolator
import androidx.core.graphics.ColorUtils
import androidx.core.graphics.PathParser

/**
 * 星火 VPN 的连接标志：锤子与镰刀沿 45° 轴对称分离，连接时向中心扣合，扣合瞬间浮出一圈
 * 很轻的脉冲光环，外沿的暗红圆环随之闭合并转为金色 —— 表示连接已经建立。
 *
 * 视觉语言与官网、Windows 端完全一致：**等线宽的空心线框 + 三层金色辉光**。
 * 形体不靠线宽变化，而靠轮廓自身的宽窄（刃身宽、刃尖收窄、握球比柄粗、锤头是块面）来区分，
 * 因此锤与镰的视觉重量是平衡的，单看任一半也能认出是什么农具。
 *
 * 时序（总时长约 1.6s，落在设计要求的 1.2s～1.8s 区间）：
 *  1. 常驻        中央一个淡淡的圆环，锤镰以极淡的线框分列两侧
 *  2. 0–900ms     两组沿 45° 轴向中心滑拢，各带约 10° 的回正旋转与末段吸附
 *  3. 120ms 起    轮廓由线条逐段「勾勒成形」（短轮廓先画完，形成错落节奏）
 *  4. ~950ms      中心扣合，脉冲光环由内向外扩散一次
 *  5. 0–1250ms    暗红圆环沿外沿慢慢闭合
 *  6. 950ms 起    黑色圆盘浮起、线条转金并浮出辉光、背后出现一层很淡的放射纹
 *
 * 路径数据与 `res/drawable/ic_xingsui_emblem.xml`、官网 SITE_HTML 逐字符同源；
 * 改动任何一处都要同步其余两处，否则三端标志会漂移。
 */
class XingsuiEmblemView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : View(context, attrs, defStyleAttr) {

    enum class Phase { IDLE, CONNECTING, CONNECTED, LOST }

    private companion object {
        const val CENTER = 100f

        /** 视图半径映射到的设计半径：放射纹到 116、脉冲最大到 120，取 120 排版最紧凑。 */
        const val OUTER = 120f

        const val R_GUIDE = 96f
        const val R_DOTTED = 68f
        const val R_DISC = 84f
        const val R_RING = 90f
        const val R_PULSE_FROM = 62f
        const val R_PULSE_TO = 120f

        // ---- 轮廓（200×200 设计坐标） ----
        const val BLADE = "M126 38A57.29 57.29 0 0 1 136 150A80.78 80.78 0 0 0 126 38Z"
        const val GRIP = "M68.72 159.97L130.54 155.48A7.5 7.5 0 0 0 130.06 140.5L68.08 140A10 10 0 1 0 68.72 159.97Z"
        const val SHAFT = "M75.51 88.82L135.2 145.09A7 7 0 0 0 144.92 135.03L86.63 77.31L75.51 88.82Z"
        const val HEAD = "M94.27 53.64L102.77 68.36A2 2 0 0 1 102.03 71.09L60.47 95.09A2 2 0 0 1 57.73 94.36L49.23 79.64A2 2 0 0 1 49.97 76.91L91.53 52.91A2 2 0 0 1 94.27 53.64Z"
        const val STUD = "M47.5 86A4.5 4.5 0 1 0 56.5 86A4.5 4.5 0 1 0 47.5 86Z"

        /** 统一线宽；形体差异全部交给轮廓本身。 */
        const val STROKE = 5.4f

        /** 三层辉光的线宽与不透明度。 */
        val GLOW_LAYERS = arrayOf(16.4f to 0.16f, 12.4f to 0.26f, 8.8f to 0.42f)

        /** 比最长的一条轮廓（刃 ≈282）还长，短轮廓因而先画完 —— 与官网 CSS 取值一致。 */
        const val DASH = 300f

        /** 未连接时两组沿 45° 轴各自拉开的距离与倾角。 */
        const val SPLIT = 26f
        const val SPLIT_TILT = 10f

        /** 分离态线框的透明度：不至于是一片空白，扣合时又会自然让位给实色。 */
        const val IDLE_ALPHA = 0.22f

        // 品牌色（与 values/colors.xml、官网 CSS 变量一致）
        const val INK = 0xFF0D0D0C.toInt()
        const val GOLD = 0xFFA8801F.toInt()
        const val GOLD_LIGHT = 0xFFF5D68C.toInt()
        const val GOLD_GLOW = 0xFFF0C874.toInt()
        const val RED = 0xFF8E1B13.toInt()

        const val ASSEMBLE_MS = 900L
        const val TRACE_DELAY_MS = 120L
        const val TRACE_MS = 780L
        const val SNAP_AT_MS = 950L
        const val RING_MS = 1250L
        const val LOCK_DELAY_MS = 950L
        const val LOCK_MS = 620L
        const val PULSE_MS = 700L
        const val RELEASE_MS = 460L
    }

    // ---- 动画进度 ----
    private var assemble = 0f   // 0 = 完全分离，1 = 扣合到位
    private var trace = 0f      // 线条勾勒进度
    private var ring = 0f       // 外沿圆环闭合进度
    private var lock = 0f       // 连接完成度：黑盘 / 转金 / 辉光 / 放射纹
    private var pulse = -1f     // < 0 表示当前没有脉冲
    private var breathe = 0f    // 连接后的呼吸

    private var phase = Phase.IDLE
    private val animators = mutableListOf<ValueAnimator>()
    private var breatheAnimator: ValueAnimator? = null

    // ---- 几何 ----
    private val sickle = listOf(BLADE, GRIP).map(PathParser::createPathFromPathData)
    private val hammer = listOf(SHAFT, HEAD, STUD).map(PathParser::createPathFromPathData)

    private val scratch = Path()
    private val matrix = Matrix()
    private val ringRect = RectF()

    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val thinPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }

    private var unit = 0f  // 一个设计单位等于多少像素
    private var cx = 0f
    private var cy = 0f

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        cx = w / 2f
        cy = h / 2f
        unit = (minOf(w, h) / 2f) / OUTER
    }

    private fun px(designValue: Float) = designValue * unit

    private fun mapX(value: Float) = cx + (value - CENTER) * unit

    private fun mapY(value: Float) = cy + (value - CENTER) * unit

    // ==================== 状态机 ====================

    fun currentPhase(): Phase = phase

    fun setPhase(next: Phase, animate: Boolean = true) {
        if (phase == next) return
        phase = next
        cancelAnimators()
        when (next) {
            Phase.CONNECTING -> if (animate) playConnecting() else snapTo(1f, 1f, 1f, 0f)
            Phase.CONNECTED -> if (animate) playConnected() else {
                snapTo(1f, 1f, 1f, 1f)
                startBreathing()
            }
            Phase.IDLE, Phase.LOST -> if (animate) playRelease() else snapTo(0f, 0f, 0f, 0f)
        }
    }

    private fun snapTo(a: Float, t: Float, r: Float, l: Float) {
        assemble = a
        trace = t
        ring = r
        lock = l
        pulse = -1f
        invalidate()
    }

    private fun playConnecting() {
        stopBreathing()
        lock = 0f
        animate(ASSEMBLE_MS, 0L, MagneticInterpolator()) { assemble = it }
        animate(TRACE_MS, TRACE_DELAY_MS, DecelerateInterpolator(1.4f)) { trace = it }
        animate(RING_MS, 0L, AccelerateDecelerateInterpolator()) { ring = it }
        animate(PULSE_MS, SNAP_AT_MS, DecelerateInterpolator(1.6f)) { pulse = it }
    }

    private fun playConnected() {
        // 从当前进度接着走，避免「连接中 → 已连接」时画面跳一下
        val resuming = assemble < 1f
        if (resuming) {
            animate(ASSEMBLE_MS, 0L, MagneticInterpolator(), from = assemble) { assemble = it }
            animate(TRACE_MS, TRACE_DELAY_MS, DecelerateInterpolator(1.4f), from = trace) { trace = it }
            animate(PULSE_MS, SNAP_AT_MS, DecelerateInterpolator(1.6f)) { pulse = it }
        } else if (lock <= 0f) {
            animate(PULSE_MS, 0L, DecelerateInterpolator(1.6f)) { pulse = it }
        }
        animate(RING_MS, 0L, AccelerateDecelerateInterpolator(), from = ring) { ring = it }
        animate(LOCK_MS, if (resuming) LOCK_DELAY_MS else 60L, DecelerateInterpolator(), from = lock) {
            lock = it
            if (it >= 1f) startBreathing()
        }
    }

    /** 断开 / 回到未连接：锤镰重新分离，圆环退回，比连接过程快一倍。 */
    private fun playRelease() {
        stopBreathing()
        pulse = -1f
        val fromAssemble = assemble
        val fromTrace = trace
        val fromRing = ring
        val fromLock = lock
        animate(RELEASE_MS, 0L, AccelerateDecelerateInterpolator()) { progress ->
            val back = 1f - progress
            assemble = fromAssemble * back
            trace = fromTrace * back
            ring = fromRing * back
            lock = fromLock * back
        }
    }

    private fun animate(
        duration: Long,
        delay: Long,
        interpolator: TimeInterpolator,
        from: Float = 0f,
        onUpdate: (Float) -> Unit,
    ) {
        val animator = ValueAnimator.ofFloat(from, 1f).apply {
            this.duration = duration
            this.startDelay = delay
            this.interpolator = interpolator
            addUpdateListener {
                onUpdate(it.animatedValue as Float)
                invalidate()
            }
        }
        animators += animator
        animator.start()
    }

    private fun cancelAnimators() {
        animators.forEach { it.cancel() }
        animators.clear()
    }

    private fun startBreathing() {
        if (breatheAnimator?.isRunning == true) return
        breatheAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 2600L
            repeatCount = ValueAnimator.INFINITE
            repeatMode = ValueAnimator.REVERSE
            interpolator = AccelerateDecelerateInterpolator()
            addUpdateListener {
                breathe = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    private fun stopBreathing() {
        breatheAnimator?.cancel()
        breatheAnimator = null
        breathe = 0f
    }

    override fun onDetachedFromWindow() {
        cancelAnimators()
        stopBreathing()
        super.onDetachedFromWindow()
    }

    // ==================== 绘制 ====================

    override fun onDraw(canvas: Canvas) {
        if (unit <= 0f) return
        drawGuides(canvas)
        if (lock > 0f) {
            drawRays(canvas)
            drawDisc(canvas)
        }
        drawRing(canvas)
        if (pulse in 0f..1f) drawPulse(canvas)
        drawEmblem(canvas)
    }

    /** 常驻的淡圆环与构成主义参考线：连接前场上主要就是它。 */
    private fun drawGuides(canvas: Canvas) {
        val fade = (1f - lock).coerceIn(0f, 1f)
        thinPaint.pathEffect = null
        thinPaint.strokeCap = Paint.Cap.BUTT
        thinPaint.strokeWidth = px(1f)

        thinPaint.color = alpha(INK, 0.10f)
        canvas.drawCircle(cx, cy, px(R_GUIDE), thinPaint)

        thinPaint.color = alpha(INK, 0.09f * fade)
        thinPaint.pathEffect = DashPathEffect(floatArrayOf(px(1f), px(5f)), 0f)
        canvas.drawCircle(cx, cy, px(R_DOTTED), thinPaint)
        thinPaint.pathEffect = null

        thinPaint.color = alpha(INK, 0.07f * fade)
        canvas.drawLine(mapX(4f), cy, mapX(196f), cy, thinPaint)
        canvas.drawLine(cx, mapY(4f), cx, mapY(196f), thinPaint)
    }

    /** 连接完成后背后那层很淡的放射纹。 */
    private fun drawRays(canvas: Canvas) {
        thinPaint.pathEffect = null
        thinPaint.strokeCap = Paint.Cap.BUTT
        thinPaint.strokeWidth = px(1f)
        thinPaint.color = alpha(GOLD, 0.24f * lock)
        for (index in 0 until 36) {
            val angle = Math.toRadians((index * 10).toDouble())
            val inner = px(92f)
            val outer = px(if (index % 3 == 0) 116f else 104f)
            canvas.drawLine(
                cx + (Math.cos(angle) * inner).toFloat(), cy + (Math.sin(angle) * inner).toFloat(),
                cx + (Math.cos(angle) * outer).toFloat(), cy + (Math.sin(angle) * outer).toFloat(),
                thinPaint,
            )
        }
    }

    /** 黑色圆盘：连接后才浮起，让金色锤镰落在黑底上。 */
    private fun drawDisc(canvas: Canvas) {
        fillPaint.color = alpha(INK, lock)
        canvas.drawCircle(cx, cy, px(R_DISC) * (0.92f + 0.08f * lock), fillPaint)
    }

    /** 外沿圆环：连接中是暗红并慢慢闭合，连接后转金。 */
    private fun drawRing(canvas: Canvas) {
        val radius = px(R_RING)
        ringRect.set(cx - radius, cy - radius, cx + radius, cy + radius)

        thinPaint.pathEffect = null
        thinPaint.strokeCap = Paint.Cap.BUTT
        thinPaint.strokeWidth = px(2f)
        thinPaint.color = alpha(if (lock > 0.5f) GOLD else INK, 0.12f + 0.10f * lock)
        canvas.drawArc(ringRect, 0f, 360f, false, thinPaint)

        if (ring <= 0f) return
        thinPaint.strokeWidth = px(2.6f)
        thinPaint.strokeCap = Paint.Cap.ROUND
        thinPaint.color = alpha(
            ColorUtils.blendARGB(RED, GOLD_LIGHT, lock),
            (0.85f + 0.15f * lock) * (1f - 0.12f * breathe),
        )
        canvas.drawArc(ringRect, -90f, 360f * ring, false, thinPaint)
    }

    /** 扣合瞬间那一圈很轻的脉冲光环。 */
    private fun drawPulse(canvas: Canvas) {
        thinPaint.pathEffect = null
        thinPaint.strokeCap = Paint.Cap.BUTT
        thinPaint.strokeWidth = px(2f)
        thinPaint.color = alpha(GOLD_LIGHT, 0.85f * (1f - pulse))
        canvas.drawCircle(cx, cy, px(R_PULSE_FROM + (R_PULSE_TO - R_PULSE_FROM) * pulse), thinPaint)
    }

    private fun drawEmblem(canvas: Canvas) {
        val back = 1f - assemble
        val breatheScale = 1f + 0.014f * breathe * lock
        val split = px(SPLIT) * back
        val tilt = SPLIT_TILT * back

        // 镰刀：分离时沿 45° 轴退到右下
        canvas.save()
        canvas.scale(breatheScale, breatheScale, cx, cy)
        canvas.translate(split, split)
        canvas.rotate(tilt, cx, cy)
        drawPart(canvas, sickle)
        canvas.restore()

        // 锤子：分离时沿同一根轴退到左上，与镰刀对称对峙
        canvas.save()
        canvas.scale(breatheScale, breatheScale, cx, cy)
        canvas.translate(-split, -split)
        canvas.rotate(-tilt, cx, cy)
        drawPart(canvas, hammer)
        canvas.restore()
    }

    /**
     * 一个部件 = 三层辉光 + 一层剪影 + 一层实线，全部走同一组轮廓。
     *
     * 未连接时看见的是**剪影**：轮廓始终画满、但很淡。扣合一开始它随 [assemble] 淡出，
     * 把画面交给正在逐段勾勒（[trace]）的实色描边 —— 否则 dash 偏移会让待机画面一片空白。
     * 辉光只在连接完成后（[lock]）浮现。
     */
    private fun drawPart(canvas: Canvas, paths: List<Path>) {
        val dash = px(DASH)
        val effect = if (trace >= 1f) null else DashPathEffect(
            floatArrayOf(dash, dash),
            dash * (1f - trace),
        )
        val settled = assemble.coerceIn(0f, 1f)

        val ghost = alpha(INK, IDLE_ALPHA * (1f - settled))
        if (ghost ushr 24 > 2) {
            paths.forEach { drawStroke(canvas, it, STROKE, ghost, null) }
        }

        if (lock > 0f) {
            for ((width, layerAlpha) in GLOW_LAYERS) {
                val color = alpha(GOLD_GLOW, layerAlpha * lock)
                paths.forEach { drawStroke(canvas, it, width, color, effect) }
            }
        }
        val core = alpha(ColorUtils.blendARGB(INK, GOLD_LIGHT, lock), settled)
        paths.forEach { drawStroke(canvas, it, STROKE, core, effect) }
    }

    private fun drawStroke(canvas: Canvas, path: Path, designWidth: Float, color: Int, effect: PathEffect?) {
        matrix.reset()
        matrix.postTranslate(-CENTER, -CENTER)
        matrix.postScale(unit, unit)
        matrix.postTranslate(cx, cy)
        scratch.reset()
        path.transform(matrix, scratch)

        strokePaint.pathEffect = effect
        strokePaint.strokeWidth = px(designWidth)
        strokePaint.color = color
        canvas.drawPath(scratch, strokePaint)
    }

    private fun alpha(color: Int, factor: Float): Int =
        ColorUtils.setAlphaComponent(color, (255f * factor.coerceIn(0f, 1f)).toInt())

    /**
     * 「吸附感」曲线：先快速接近、末段轻微越过，最后 12% 收敛回精确位置，
     * 制造两个部件被磁吸「扣上去」的顿感，而不是在中心来回抖。
     */
    private class MagneticInterpolator : TimeInterpolator {
        override fun getInterpolation(input: Float): Float {
            val t = input - 1f
            val overshoot = t * t * ((TENSION + 1f) * t + TENSION) + 1f
            if (input < SETTLE_FROM) return overshoot
            val k = (input - SETTLE_FROM) / (1f - SETTLE_FROM)
            return overshoot + (1f - overshoot) * k
        }

        private companion object {
            const val TENSION = 1.42f
            const val SETTLE_FROM = 0.88f
        }
    }
}
