package org.amnezia.awg.xingsui

import android.content.Context

object XingsuiVipGate {
    suspend fun requireFreshManagedConfig(
        context: Context,
        nodeId: String? = null,
        excludeNodeId: String? = null,
    ): FreshManagedConfig =
        XingsuiManagedConfigProvider.fetch(context, nodeId, excludeNodeId)
}
