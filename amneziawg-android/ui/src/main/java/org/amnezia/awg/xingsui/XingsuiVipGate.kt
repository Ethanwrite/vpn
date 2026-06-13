package org.amnezia.awg.xingsui

import android.content.Context
import org.amnezia.awg.R
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException

class XingsuiVipRequiredException(message: String, cause: Throwable? = null) : IllegalStateException(message, cause)

object XingsuiVipGate {
    suspend fun requireActiveVip(context: Context) {
        val session = XingsuiSessionStore(context).load()
            ?: throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_required_login))

        val entitlement = try {
            XingsuiApiClient(accessToken = session.accessToken).authorizeVpn()
        } catch (e: Throwable) {
            if (e.isUnauthorized()) {
                XingsuiSessionStore(context).clear()
                throw XingsuiVipRequiredException(context.getString(R.string.xingsui_session_expired), e)
            }
            throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_verify_failed), e)
        }

        if (entitlement.allowed) {
            try {
                XingsuiApiClient(accessToken = session.accessToken).getDefaultVpnConfig()
            } catch (e: Throwable) {
                if (e.isUnauthorized()) {
                    XingsuiSessionStore(context).clear()
                    throw XingsuiVipRequiredException(context.getString(R.string.xingsui_session_expired), e)
                }
                throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_verify_failed), e)
            }
            return
        }

        when (entitlement.reason) {
            REASON_VIP_EXPIRED -> throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_expired))
            REASON_FREE_TRAFFIC_EXHAUSTED -> throw XingsuiVipRequiredException(context.getString(R.string.xingsui_free_trial_exhausted))
            REASON_VIP_REQUIRED -> throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_required_active))
            else -> throw XingsuiVipRequiredException(context.getString(R.string.xingsui_vip_required_active))
        }
    }

    private const val REASON_VIP_EXPIRED = "vip_expired"
    private const val REASON_FREE_TRAFFIC_EXHAUSTED = "free_traffic_exhausted"
    private const val REASON_VIP_REQUIRED = "vip_required"

    private fun Throwable.isUnauthorized(): Boolean =
        (this as? XingsuiHttpException)?.isUnauthorized == true ||
            (cause as? XingsuiHttpException)?.isUnauthorized == true
}
