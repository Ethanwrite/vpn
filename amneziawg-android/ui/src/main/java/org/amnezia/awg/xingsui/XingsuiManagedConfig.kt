package org.amnezia.awg.xingsui

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.amnezia.awg.R
import org.amnezia.awg.config.Config
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException
import org.amnezia.awg.xingsui.model.VpnNodeConfig
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.nio.charset.StandardCharsets
import java.time.Duration
import java.time.Instant
import java.util.Locale

data class FreshManagedConfig(
    val response: VpnNodeConfig,
    val config: Config,
)

class XingsuiConnectionSyncException(message: String) : IllegalStateException(message)

/**
 * Thrown when the backend refuses a VPN config for an authorized-but-denied reason
 * (free traffic exhausted / VIP expired / VIP required). This is a normal product
 * outcome — the UI should prompt the user to open VIP, NOT report a sync failure.
 */
class XingsuiEntitlementException(val reason: String) : IllegalStateException(reason)

object XingsuiManagedConfigProvider {
    suspend fun fetch(
        context: Context,
        nodeId: String? = null,
        excludeNodeId: String? = null,
    ): FreshManagedConfig = withContext(Dispatchers.IO) {
        try {
            val sessionStore = XingsuiSessionStore(context)
            val session = sessionStore.load() ?: throw IllegalStateException("missing_session")
            val api = XingsuiApiClient(accessToken = session.accessToken)
            val response = if (nodeId.isNullOrBlank()) {
                api.getDefaultVpnConfig(excludeNodeId = excludeNodeId)
            } else {
                require(NODE_ID_PATTERN.matches(nodeId)) { "managed_node_id_rejected" }
                api.getNodeConfig(nodeId)
            }
            XingsuiManagedConfigValidator.validate(response)
            // Keep the app's own control-plane traffic (login, /usage/report lease renewal,
            // failover probes) OFF the tunnel: a dead data path must not take down the
            // API channel that reports and recovers from it.
            val configText = withOwnAppExcluded(response.configText, context.packageName)
            val parsed = ByteArrayInputStream(configText.toByteArray(StandardCharsets.UTF_8)).use {
                Config.parse(it)
            }
            require(parsed.peers.size == 1) { "managed_config_requires_one_peer" }
            FreshManagedConfig(response, parsed)
        } catch (error: Throwable) {
            if (error is CancellationException) throw error
            val httpError = error as? XingsuiHttpException ?: error.cause as? XingsuiHttpException
            if (httpError?.isUnauthorized == true) {
                XingsuiSessionStore(context).clear()
            }
            entitlementDenialReason(httpError)?.let { reason ->
                // Denied by entitlement (e.g. free traffic exhausted): surface the real
                // reason so the UI can prompt for VIP instead of "账户状态同步失败".
                throw XingsuiEntitlementException(reason)
            }
            XingsuiCrashReporter.recordEvent(
                "managed-config-fetch-failed",
                error.javaClass.simpleName.ifBlank { "unknown" },
            )
            throw XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
        }
    }

    /**
     * Inserts `ExcludedApplications = <own package>` into the [Interface] section so the
     * client's own traffic bypasses the tunnel. Runs after server-config validation; skipped
     * if the server ever starts sending its own exclusion list (avoids duplicate keys).
     */
    private fun withOwnAppExcluded(configText: String, packageName: String): String {
        if (configText.contains("excludedapplications", ignoreCase = true)) return configText
        val lines = configText.lines().toMutableList()
        val interfaceIndex = lines.indexOfFirst { it.trim().equals("[Interface]", ignoreCase = true) }
        if (interfaceIndex < 0) return configText
        lines.add(interfaceIndex + 1, "ExcludedApplications = $packageName")
        return lines.joinToString("\n")
    }

    /**
     * The VPN config endpoints reply `403 {"detail":"<reason>"}` when entitlement is
     * denied (see backend `get_vpn_config` / `get_vpn_node_config`). Returns the reason
     * only for known entitlement denials; other 403s (disabled node, protocol mismatch)
     * stay generic sync failures.
     */
    private fun entitlementDenialReason(httpError: XingsuiHttpException?): String? {
        if (httpError?.statusCode != 403) return null
        val detail = runCatching { JSONObject(httpError.responseBody).optString("detail") }
            .getOrNull()
            ?.trim()
            .orEmpty()
        return detail.takeIf { it in ENTITLEMENT_DENIAL_REASONS }
    }

    private val ENTITLEMENT_DENIAL_REASONS =
        setOf("free_traffic_exhausted", "vip_expired", "vip_required")

    private val NODE_ID_PATTERN = Regex("[A-Za-z0-9._-]{1,64}")
}

object XingsuiManagedConfigValidator {
    private val requiredInterfaceKeys = setOf(
        "PrivateKey",
        "Address",
        "DNS",
        "MTU",
        "Jc",
        "Jmin",
        "Jmax",
        "S1",
        "S2",
        "H1",
        "H2",
        "H3",
        "H4",
    )
    private val requiredPeerKeys = setOf(
        "PublicKey",
        "AllowedIPs",
        "Endpoint",
        "PersistentKeepalive",
    )

    fun validate(response: VpnNodeConfig, now: Instant = Instant.now()) {
        require(response.entitlement.allowed) { "managed_config_entitlement_denied" }
        require(response.protocol.trim().lowercase(Locale.US) == PROTOCOL_AMNEZIAWG) {
            "managed_config_protocol_rejected"
        }
        require(LEASE_ID_PATTERN.matches(response.leaseId)) { "managed_config_lease_id_rejected" }
        require(!response.issuedAt.isAfter(now.plus(MAX_CLOCK_SKEW))) { "managed_config_issued_in_future" }
        require(!response.issuedAt.isBefore(now.minus(MAX_ISSUE_AGE))) { "managed_config_issue_too_old" }
        require(response.expiresAt.isAfter(now) && response.expiresAt.isAfter(response.issuedAt)) {
            "managed_config_expired"
        }
        val leaseDuration = Duration.between(response.issuedAt, response.expiresAt)
        require(leaseDuration <= MAX_LEASE_DURATION) { "managed_config_lease_too_long" }
        response.entitlement.leaseExpiresAt?.let {
            require(it == response.expiresAt) { "managed_config_entitlement_lease_mismatch" }
        }
        validateConfigText(response.configText)
    }

    fun validateConfigText(configText: String) {
        require(configText.isNotBlank() && configText.length <= MAX_CONFIG_TEXT_LENGTH) {
            "managed_config_size_rejected"
        }
        val lowered = configText.lowercase(Locale.US)
        require(NON_AWG_URI_SCHEMES.none(lowered::contains)) { "managed_config_uri_rejected" }

        var section: String? = null
        var interfaceSections = 0
        var peerSections = 0
        val interfaceValues = linkedMapOf<String, String>()
        val peerValues = linkedMapOf<String, String>()

        configText.lineSequence().forEach { rawLine ->
            val line = rawLine.trim()
            if (line.isEmpty() || line.startsWith("#") || line.startsWith(";")) return@forEach
            if (line.startsWith("[") && line.endsWith("]")) {
                section = line.substring(1, line.length - 1).trim()
                when (section) {
                    SECTION_INTERFACE -> interfaceSections++
                    SECTION_PEER -> peerSections++
                    else -> throw IllegalArgumentException("managed_config_section_rejected")
                }
                return@forEach
            }

            val separator = line.indexOf('=')
            require(separator > 0) { "managed_config_line_rejected" }
            val key = line.substring(0, separator).trim()
            val value = line.substring(separator + 1).trim()
            require(key.isNotEmpty() && value.isNotEmpty()) { "managed_config_value_missing" }
            val target = when (section) {
                SECTION_INTERFACE -> interfaceValues
                SECTION_PEER -> peerValues
                else -> throw IllegalArgumentException("managed_config_top_level_rejected")
            }
            require(target.put(key, value) == null) { "managed_config_duplicate_key" }
        }

        require(interfaceSections == 1 && peerSections == 1) { "managed_config_section_count_rejected" }
        require(interfaceValues.keys.containsAll(requiredInterfaceKeys)) { "managed_config_interface_incomplete" }
        require(peerValues.keys.containsAll(requiredPeerKeys)) { "managed_config_peer_incomplete" }

        val allowedIps = peerValues.getValue("AllowedIPs")
            .split(',')
            .map(String::trim)
            .filter(String::isNotEmpty)
            .toSet()
        require(IPV4_DEFAULT_ROUTE in allowedIps && IPV6_DEFAULT_ROUTE in allowedIps) {
            "managed_config_default_routes_incomplete"
        }
    }

    private const val PROTOCOL_AMNEZIAWG = "amneziawg"
    private const val SECTION_INTERFACE = "Interface"
    private const val SECTION_PEER = "Peer"
    private const val IPV4_DEFAULT_ROUTE = "0.0.0.0/0"
    private const val IPV6_DEFAULT_ROUTE = "::/0"
    private const val MAX_CONFIG_TEXT_LENGTH = 32 * 1024
    private val MAX_LEASE_DURATION: Duration = Duration.ofMinutes(15)
    private val MAX_CLOCK_SKEW: Duration = Duration.ofMinutes(1)
    private val MAX_ISSUE_AGE: Duration = Duration.ofMinutes(5)
    private val LEASE_ID_PATTERN = Regex("[A-Za-z0-9_-]{1,64}")
    private val NON_AWG_URI_SCHEMES = listOf("vless://", "vmess://", "trojan://", "ss://")
}
