package org.amnezia.awg.xingsui

import org.amnezia.awg.xingsui.model.EntitlementStatus
import org.amnezia.awg.xingsui.model.VpnNodeConfig
import org.junit.Assert.assertThrows
import org.junit.Test
import java.time.Instant
import java.time.temporal.ChronoUnit

class XingsuiManagedConfigValidatorTest {
    private val now = Instant.parse("2026-07-10T12:00:00Z")

    @Test
    fun acceptsShortLivedAmneziaWgConfigWithDualStackKillSwitch() {
        XingsuiManagedConfigValidator.validate(validResponse(), now)
    }

    @Test
    fun rejectsVlessAndOtherProtocols() {
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(validResponse().copy(protocol = "vless"), now)
        }
    }

    @Test
    fun rejectsFreeTrialEntitlement() {
        val freeTrial = validEntitlement().copy(vipStatus = "inactive", vipExpiredAt = null)
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(validResponse().copy(entitlement = freeTrial), now)
        }
    }

    @Test
    fun rejectsExpiredOrLongLivedLease() {
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(validResponse().copy(expiresAt = now.minusSeconds(1)), now)
        }
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(validResponse().copy(expiresAt = now.plus(16, ChronoUnit.MINUTES)), now)
        }
    }

    @Test
    fun rejectsMalformedOrStaleLeaseIdentity() {
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(validResponse().copy(leaseId = "../lease"), now)
        }
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validate(
                validResponse().copy(issuedAt = now.minus(6, ChronoUnit.MINUTES)),
                now,
            )
        }
    }

    @Test
    fun rejectsMissingRequiredField() {
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validateConfigText(
                validConfigText().replace("DNS = 1.1.1.1\n", "")
            )
        }
    }

    @Test
    fun rejectsMissingIpv6DefaultRoute() {
        assertThrows(IllegalArgumentException::class.java) {
            XingsuiManagedConfigValidator.validateConfigText(
                validConfigText().replace("0.0.0.0/0, ::/0", "0.0.0.0/0")
            )
        }
    }

    private fun validResponse() = VpnNodeConfig(
        id = "test-node",
        name = "Test node",
        region = "Test region",
        tunnelName = "xingsui",
        protocol = "amneziawg",
        leaseId = "lease-test-1",
        issuedAt = now,
        expiresAt = now.plus(5, ChronoUnit.MINUTES),
        configText = validConfigText(),
        entitlement = validEntitlement(),
    )

    private fun validEntitlement() = EntitlementStatus(
        allowed = true,
        reason = "vip_active",
        vipStatus = "active",
        vipExpiredAt = now.plus(30, ChronoUnit.DAYS),
        freeTrafficQuotaBytes = 0,
        freeTrafficUsedBytes = 0,
        freeTrafficRemainingBytes = 0,
        leaseExpiresAt = now.plus(5, ChronoUnit.MINUTES),
    )

    private fun validConfigText() = """
        [Interface]
        PrivateKey = test-private-key
        Address = 10.0.0.2/32
        DNS = 1.1.1.1
        MTU = 1280
        Jc = 4
        Jmin = 40
        Jmax = 70
        S1 = 86
        S2 = 574
        H1 = 11
        H2 = 22
        H3 = 33
        H4 = 44

        [Peer]
        PublicKey = test-public-key
        AllowedIPs = 0.0.0.0/0, ::/0
        Endpoint = vpn.invalid:443
        PersistentKeepalive = 25
    """.trimIndent()
}
