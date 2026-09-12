package org.amnezia.awg.xingsui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class XingsuiCarouselGeometryTest {
    @Test fun cardsStayWithinRequestedProportionAndPeekOnPhoneScreens() {
        for (density in listOf(1f, 2f, 3f)) for (dpWidth in listOf(360, 390, 420, 480)) {
            val width = (dpWidth * density).toInt()
            val geometry = XingsuiCarouselGeometry.forViewport(width, density)
            assertTrue(geometry.cardWidth.toFloat() / width in .82f.. .86f)
            val left = geometry.edgePadding + geometry.cardMargin
            val nextCardStart = left + geometry.cardWidth + geometry.cardMargin * 2
            val peek = (width - nextCardStart) / density
            assertTrue("Visible next-card edge must be 20–35 dp, got $peek", peek in 20f..35f)
            assertEquals(width / 2f, left + geometry.cardWidth / 2f, 1f)
        }
    }
    @Test fun firstAndLastCardsCanBothReachTheViewportCenter() {
        val width = 1080
        val g = XingsuiCarouselGeometry.forViewport(width, 3f)
        for (count in listOf(1, 2, 3, 5)) {
            val decorated = g.cardWidth + g.cardMargin * 2
            val contentWidth = count * decorated + 2 * g.edgePadding
            val maxScroll = (contentWidth - width).coerceAtLeast(0)
            val lastCenter = g.edgePadding + (count - 1) * decorated + g.cardMargin + g.cardWidth / 2f - maxScroll
            assertEquals(width / 2f, lastCenter, 1f)
        }
    }
}
