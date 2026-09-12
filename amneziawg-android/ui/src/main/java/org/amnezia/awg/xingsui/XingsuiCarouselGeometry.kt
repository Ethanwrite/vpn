package org.amnezia.awg.xingsui

import kotlin.math.roundToInt

internal data class XingsuiCarouselGeometry(val cardWidth: Int, val edgePadding: Int, val cardMargin: Int) {
    companion object {
        fun forViewport(width: Int, density: Float): XingsuiCarouselGeometry {
            require(width > 0 && density > 0)
            val card = (width * .84f).roundToInt()
            val side = (width - card) / 2
            val margin = maxOf(3f * density, (side - 28f * density) / 2f).roundToInt()
            return XingsuiCarouselGeometry(card, (side - margin).coerceAtLeast(0), margin)
        }
    }
}
