package org.amnezia.awg.xingsui.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import android.util.Log
import org.amnezia.awg.BuildConfig
import org.amnezia.awg.xingsui.AuthSession
import org.amnezia.awg.xingsui.XingsuiCrashReporter
import org.amnezia.awg.xingsui.model.EntitlementStatus
import org.amnezia.awg.xingsui.model.AppVersionInfo
import org.amnezia.awg.xingsui.model.InvitationSummary
import org.amnezia.awg.xingsui.model.OrderStatus
import org.amnezia.awg.xingsui.model.OrderSummary
import org.amnezia.awg.xingsui.model.PayChannel
import org.amnezia.awg.xingsui.model.PromotionActivity
import org.amnezia.awg.xingsui.model.UserAccount
import org.amnezia.awg.xingsui.model.VipPlan
import org.amnezia.awg.xingsui.model.VpnNodeConfig
import org.amnezia.awg.xingsui.model.VpnNodeSummary
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.time.OffsetDateTime

class XingsuiApiClient(
    baseUrl: String = BuildConfig.XINGSUI_API_BASE_URL.trimEnd('/'),
    private val accessToken: String? = null,
) {
    private val baseUrls: List<String> = buildApiBaseUrls(baseUrl)

    suspend fun register(email: String, password: String, inviteCode: String?): AuthSession = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("email", email)
            .put("password", password)
        if (!inviteCode.isNullOrBlank()) {
            body.put("invite_code", inviteCode.trim())
        }
        JSONObject(request("POST", "/auth/email/register", body.toString())).toAuthSession()
    }

    suspend fun login(email: String, password: String): AuthSession = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("email", email)
            .put("password", password)
        JSONObject(request("POST", "/auth/email/login", body.toString())).toAuthSession()
    }

    suspend fun listPlans(): List<VipPlan> = withContext(Dispatchers.IO) {
        val response = request("GET", "/plans")
        val plans = JSONArray(response)
        buildList {
            for (index in 0 until plans.length()) {
                add(plans.getJSONObject(index).toVipPlan())
            }
        }
    }

    suspend fun getActivePromotion(): PromotionActivity? = withContext(Dispatchers.IO) {
        runCatching {
            JSONObject(request("GET", "/promotions/active")).toPromotionActivity()
        }.getOrNull()
    }

    suspend fun createOrder(
        planId: String,
        promotionId: String?,
        payChannel: PayChannel,
    ): OrderSummary = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("plan_id", planId)
            .put("pay_channel", payChannel.apiName)
        if (promotionId != null) {
            body.put("promotion_id", promotionId)
        }
        JSONObject(request("POST", "/orders", body.toString())).toOrderSummary()
    }

    suspend fun markOrderPaid(orderId: String): OrderSummary = withContext(Dispatchers.IO) {
        JSONObject(request("POST", "/orders/$orderId/paid")).toOrderSummary()
    }

    suspend fun getInvitationSummary(): InvitationSummary = withContext(Dispatchers.IO) {
        JSONObject(request("GET", "/invitations/me")).toInvitationSummary()
    }

    suspend fun getMe(): UserAccount = withContext(Dispatchers.IO) {
        JSONObject(request("GET", "/me")).toUserAccount()
    }

    suspend fun getAppVersion(currentVersionCode: Int): AppVersionInfo = withContext(Dispatchers.IO) {
        JSONObject(request("GET", "/app/version?version_code=$currentVersionCode")).toAppVersionInfo()
    }

    suspend fun getDefaultVpnConfig(rotate: Boolean = false): VpnNodeConfig = withContext(Dispatchers.IO) {
        val path = if (rotate) "/vpn/config?rotate=true" else "/vpn/config"
        JSONObject(request("GET", path, allowFailover = false)).toVpnNodeConfig()
    }

    suspend fun listNodes(): List<VpnNodeSummary> = withContext(Dispatchers.IO) {
        val nodes = JSONArray(request("GET", "/vpn/nodes"))
        buildList {
            for (index in 0 until nodes.length()) {
                add(nodes.getJSONObject(index).toVpnNodeSummary())
            }
        }
    }

    suspend fun getNodeConfig(nodeId: String): VpnNodeConfig = withContext(Dispatchers.IO) {
        JSONObject(request("GET", "/vpn/nodes/$nodeId/config", allowFailover = false)).toVpnNodeConfig()
    }

    suspend fun reportUsage(
        leaseId: String,
        tunnelName: String,
        rxBytesDelta: Long,
        txBytesDelta: Long,
    ): EntitlementStatus = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("lease_id", leaseId)
            .put("tunnel_name", tunnelName)
            .put("rx_bytes_delta", rxBytesDelta)
            .put("tx_bytes_delta", txBytesDelta)
        JSONObject(request("POST", "/usage/report", body.toString())).toEntitlementStatus()
    }

    suspend fun createWithdrawal(amountCents: Int, accountType: String, accountMasked: String) = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("amount_cents", amountCents)
            .put("account_type", accountType)
            .put("account_masked", accountMasked)
        request("POST", "/withdrawals", body.toString())
    }

    private fun request(
        method: String,
        path: String,
        body: String? = null,
        allowFailover: Boolean = true,
    ): String {
        var lastError: Throwable? = null
        val requestBaseUrls = orderedBaseUrls().let { if (allowFailover) it else it.take(1) }
        for (requestBaseUrl in requestBaseUrls) {
            try {
                return performRequest(requestBaseUrl, method, path, body).also {
                    activeBaseUrl = requestBaseUrl
                }
            } catch (error: XingsuiHttpException) {
                // A stale API path may return 404 even though the canonical
                // production endpoint is healthy. Retry only that routing case;
                // authentication and validation failures remain authoritative.
                if (!error.isRetriable && error.statusCode != HttpURLConnection.HTTP_NOT_FOUND) throw error
                lastError = error
                Log.w(TAG, "Retriable HTTP error from $requestBaseUrl$path: ${error.statusCode}")
            } catch (error: IOException) {
                lastError = error
                Log.w(TAG, "Network error from $requestBaseUrl$path: ${error.message}")
            }
        }
        if (lastError != null) {
            XingsuiCrashReporter.recordException("api:$method:$path", lastError)
        }
        throw IllegalStateException("网络连接失败，请稍后重试或切换网络", lastError)
    }

    private fun performRequest(requestBaseUrl: String, method: String, path: String, body: String? = null): String {
        val connection = (URL("$requestBaseUrl$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method
            useCaches = false
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Cache-Control", "no-store")
            setRequestProperty("Pragma", "no-cache")
            setRequestProperty("X-Xingsui-Platform", "android")
            setRequestProperty("X-Xingsui-Version-Code", BuildConfig.VERSION_CODE.toString())
            setRequestProperty("X-Xingsui-Version-Name", BuildConfig.VERSION_NAME)
            if (accessToken != null) {
                setRequestProperty("Authorization", "Bearer $accessToken")
            }
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
        }

        return connection.use {
            val statusCode = it.responseCode
            val stream = if (statusCode in 200..299) it.inputStream else it.errorStream
            val text = if (stream != null) {
                BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
                    reader.readText()
                }
            } else {
                ""
            }
            if (statusCode !in 200..299) {
                throw XingsuiHttpException(statusCode, text)
            }
            text
        }
    }

    private fun orderedBaseUrls(): List<String> {
        val active = activeBaseUrl
        if (active != null && active in baseUrls) {
            return listOf(active) + baseUrls.filterNot { it == active }
        }
        return baseUrls
    }

    private fun JSONObject.toVipPlan() = VipPlan(
        id = getString("id"),
        name = getString("name"),
        durationDays = getInt("duration_days"),
        originalPriceCents = getInt("original_price_cents"),
        salePriceCents = getInt("sale_price_cents"),
    )

    private fun JSONObject.toAuthSession(): AuthSession {
        val user = getJSONObject("user")
        return AuthSession(
            accessToken = getString("access_token"),
            userId = user.getString("id"),
            email = user.getString("email"),
            inviteCode = user.getString("invite_code"),
        )
    }

    private fun JSONObject.toPromotionActivity() = PromotionActivity(
        id = getString("id"),
        name = getString("name"),
        tag = getString("tag"),
        planId = getString("plan_id"),
        startsAt = OffsetDateTime.parse(getString("starts_at")).toInstant(),
        endsAt = OffsetDateTime.parse(getString("ends_at")).toInstant(),
        promoPriceCents = getInt("promo_price_cents"),
        inviteExtraDiscountCents = getInt("invite_extra_discount_cents"),
        stackable = getBoolean("stackable"),
        newUserOnly = getBoolean("new_user_only"),
        countdownEnabled = getBoolean("countdown_enabled"),
    )

    private fun JSONObject.toOrderSummary() = OrderSummary(
        id = getString("id"),
        orderNo = getString("order_no"),
        planId = getString("plan_id"),
        promotionId = optString("promotion_id").takeIf { it.isNotBlank() && it != "null" },
        originalAmountCents = getInt("original_amount_cents"),
        discountAmountCents = getInt("discount_amount_cents"),
        payAmountCents = getInt("pay_amount_cents"),
        payChannel = getString("pay_channel").toPayChannel(),
        status = getString("status").toOrderStatus(),
        paymentQrUrl = getString("payment_qr_url"),
    )

    private fun JSONObject.toInvitationSummary() = InvitationSummary(
        inviteCode = getString("invite_code"),
        invitedCount = getInt("invited_count"),
        paidInviteCount = getInt("paid_invite_count"),
        totalRewardCents = getInt("total_reward_cents"),
        withdrawableBalanceCents = getInt("withdrawable_balance_cents"),
    )

    private fun JSONObject.toUserAccount() = UserAccount(
        id = getString("id"),
        email = getString("email"),
        inviteCode = getString("invite_code"),
        vipStatus = getString("vip_status"),
        vipExpiredAt = optNullableString("vip_expired_at")?.let { OffsetDateTime.parse(it).toInstant() },
        cashBalanceCents = getInt("cash_balance_cents"),
        freeTrafficQuotaBytes = getLong("free_traffic_quota_bytes"),
        freeTrafficUsedBytes = getLong("free_traffic_used_bytes"),
        freeTrafficRemainingBytes = getLong("free_traffic_remaining_bytes"),
    )

    private fun JSONObject.toAppVersionInfo() = AppVersionInfo(
        versionCode = getInt("version_code"),
        versionName = getString("version_name"),
        downloadUrl = getString("download_url"),
    )

    private fun JSONObject.toEntitlementStatus() = EntitlementStatus(
        allowed = getBoolean("allowed"),
        reason = getString("reason"),
        vipStatus = getString("vip_status"),
        vipExpiredAt = optNullableString("vip_expired_at")?.let { OffsetDateTime.parse(it).toInstant() },
        freeTrafficQuotaBytes = getLong("free_traffic_quota_bytes"),
        freeTrafficUsedBytes = getLong("free_traffic_used_bytes"),
        freeTrafficRemainingBytes = getLong("free_traffic_remaining_bytes"),
        leaseExpiresAt = optNullableString("lease_expires_at")?.let { OffsetDateTime.parse(it).toInstant() },
    )

    private fun JSONObject.toVpnNodeConfig() = VpnNodeConfig(
        id = getString("id"),
        name = getString("name"),
        region = getString("region"),
        tunnelName = getString("tunnel_name"),
        protocol = getString("protocol"),
        leaseId = getString("lease_id"),
        issuedAt = OffsetDateTime.parse(getString("issued_at")).toInstant(),
        expiresAt = OffsetDateTime.parse(getString("expires_at")).toInstant(),
        configText = getString("config_text"),
        entitlement = getJSONObject("entitlement").toEntitlementStatus(),
    )

    private fun JSONObject.toVpnNodeSummary() = VpnNodeSummary(
        id = getString("id"),
        name = getString("name"),
        region = getString("region"),
        protocol = getString("protocol"),
        vipOnly = getBoolean("vip_only"),
        status = getString("status"),
        loadPercent = getInt("load_percent"),
        locked = getBoolean("locked"),
    )

    private fun JSONObject.optNullableString(name: String): String? {
        if (isNull(name)) return null
        return optString(name).takeIf { it.isNotBlank() && it != "null" }
    }

    private fun String.toPayChannel() = when (this) {
        "alipay" -> PayChannel.Alipay
        else -> PayChannel.Wechat
    }

    private fun String.toOrderStatus() = when (this) {
        "pending_confirm" -> OrderStatus.PendingConfirm
        "completed" -> OrderStatus.Completed
        "cancelled" -> OrderStatus.Cancelled
        "rejected" -> OrderStatus.Rejected
        else -> OrderStatus.PendingPayment
    }

    private val PayChannel.apiName: String
        get() = when (this) {
            PayChannel.Wechat -> "wechat"
            PayChannel.Alipay -> "alipay"
        }

    private inline fun <T> HttpURLConnection.use(block: (HttpURLConnection) -> T): T {
        try {
            return block(this)
        } finally {
            disconnect()
        }
    }

    companion object {
        private const val TAG = "XingsuiApiClient"
        @Volatile
        private var activeBaseUrl: String? = null

        private const val CONNECT_TIMEOUT_MS = 5000
        private const val READ_TIMEOUT_MS = 7000
        private const val CANONICAL_API_BASE_URL = "https://xingsui.org"
        // Equal, independent mirror on a different domain (same backend). Some mainland
        // Wi-Fi DNS-poison / SNI-block the name "xingsui.org" (not the IP), which would
        // otherwise break in-app login/authorize/connect even though the site is up.
        private const val MIRROR_API_BASE_URL = "https://xingsuico.com"

        private fun buildApiBaseUrls(primaryBaseUrl: String): List<String> {
            val primary = primaryBaseUrl.trimEnd('/')
            // Order matters: primary host, then the mirror host (so a blocked primary
            // fails over to a different domain after one timeout, not two same-host
            // attempts), then the legacy /api path variants on each. The sticky
            // activeBaseUrl remembers whichever succeeds so later requests hit it first.
            val candidates = mutableListOf(
                primary,
                MIRROR_API_BASE_URL,
                "$CANONICAL_API_BASE_URL/api",
                "$MIRROR_API_BASE_URL/api",
            )
            return candidates.map { it.trimEnd('/') }.distinct()
        }

        /**
         * Origin (scheme://host[:port]) of the last base URL that served a request, so
         * browser links (website / recharge) and self-update downloads open on whichever
         * domain is currently reachable — primary or mirror — instead of a hardcoded one.
         * Falls back to the canonical domain before any request has succeeded.
         */
        fun activeWebOrigin(): String {
            val base = activeBaseUrl ?: CANONICAL_API_BASE_URL
            return runCatching {
                val url = URL(base)
                val port = if (url.port == -1 || url.port == url.defaultPort) "" else ":${url.port}"
                "${url.protocol}://${url.host}$port"
            }.getOrDefault(CANONICAL_API_BASE_URL)
        }
    }
}

class XingsuiHttpException(
    val statusCode: Int,
    val responseBody: String,
) : IOException("HTTP $statusCode: $responseBody") {
    val isRetriable: Boolean
        get() = statusCode == 408 || statusCode == 425 || statusCode == 429 || statusCode in 500..599

    val isUnauthorized: Boolean
        get() = statusCode == HttpURLConnection.HTTP_UNAUTHORIZED
}
