package org.amnezia.awg.xingsui.model

import java.time.Instant

data class VipPlan(
    val id: String,
    val name: String,
    val durationDays: Int,
    val originalPriceCents: Int,
    val salePriceCents: Int,
)

data class PromotionActivity(
    val id: String,
    val name: String,
    val tag: String,
    val planId: String,
    val startsAt: Instant,
    val endsAt: Instant,
    val promoPriceCents: Int,
    val inviteExtraDiscountCents: Int,
    val stackable: Boolean,
    val newUserOnly: Boolean,
    val countdownEnabled: Boolean,
)

data class OrderSummary(
    val id: String,
    val orderNo: String,
    val planId: String,
    val promotionId: String?,
    val originalAmountCents: Int,
    val discountAmountCents: Int,
    val payAmountCents: Int,
    val payChannel: PayChannel,
    val status: OrderStatus,
    val paymentQrUrl: String,
)

data class InvitationSummary(
    val inviteCode: String,
    val invitedCount: Int,
    val paidInviteCount: Int,
    val totalRewardCents: Int,
    val withdrawableBalanceCents: Int,
)

data class UserAccount(
    val id: String,
    val email: String,
    val inviteCode: String,
    val vipStatus: String,
    val vipExpiredAt: Instant?,
    val cashBalanceCents: Int,
    val freeTrafficQuotaBytes: Long,
    val freeTrafficUsedBytes: Long,
    val freeTrafficRemainingBytes: Long,
)

data class EntitlementStatus(
    val allowed: Boolean,
    val reason: String,
    val vipStatus: String,
    val vipExpiredAt: Instant?,
    val freeTrafficQuotaBytes: Long,
    val freeTrafficUsedBytes: Long,
    val freeTrafficRemainingBytes: Long,
)

data class VpnNodeConfig(
    val id: String,
    val name: String,
    val region: String,
    val tunnelName: String,
    val configText: String,
    val entitlement: EntitlementStatus,
)

data class VpnNodeSummary(
    val id: String,
    val name: String,
    val region: String,
    val vipOnly: Boolean,
    val status: String,
    val loadPercent: Int,
    val locked: Boolean,
)

enum class PayChannel {
    Wechat,
    Alipay,
}

enum class OrderStatus {
    PendingPayment,
    PendingConfirm,
    Completed,
    Cancelled,
    Rejected,
}
