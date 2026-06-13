package org.amnezia.awg.xingsui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Paint
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.getSystemService
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.launch
import org.amnezia.awg.R
import org.amnezia.awg.databinding.XingsuiVipActivityBinding
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.model.InvitationSummary
import org.amnezia.awg.xingsui.model.PromotionActivity
import org.amnezia.awg.xingsui.model.VipPlan
import java.time.Duration
import java.time.Instant
import java.util.Locale

class XingsuiVipActivity : AppCompatActivity() {
    private lateinit var apiClient: XingsuiApiClient
    private lateinit var binding: XingsuiVipActivityBinding
    private lateinit var session: AuthSession
    private lateinit var sessionStore: XingsuiSessionStore
    private var activePromotion: PromotionActivity? = null
    private var monthlyPlan: VipPlan? = null
    private var withdrawableBalanceCents = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = XingsuiVipActivityBinding.inflate(layoutInflater)
        sessionStore = XingsuiSessionStore(this)
        val loadedSession = sessionStore.load()
        if (loadedSession == null) {
            startActivity(Intent(this, XingsuiAuthActivity::class.java))
            finish()
            return
        }
        session = loadedSession
        apiClient = XingsuiApiClient(accessToken = session.accessToken)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.originalPrice.paintFlags = binding.originalPrice.paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
        binding.submitPaid.isEnabled = true
        binding.submitPaid.setOnClickListener {
            openWebsiteRecharge()
        }
        binding.copyInvite.setOnClickListener {
            copyInviteCode()
        }
        binding.submitAlipayWithdrawal.setOnClickListener {
            lifecycleScope.launch { submitAlipayWithdrawal() }
        }
        binding.copyWithdrawWechat.setOnClickListener {
            copyWithdrawWechat()
        }
        binding.inviteCode.text = getString(R.string.xingsui_invite_code_template, session.inviteCode)
        lifecycleScope.launch { loadCommercialData() }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private suspend fun loadCommercialData() {
        binding.orderStatus.setText(R.string.xingsui_order_loading)
        runCatching {
            val plans = apiClient.listPlans()
            monthlyPlan = plans.firstOrNull { it.id == MONTHLY_PLAN_ID } ?: plans.first()
            activePromotion = apiClient.getActivePromotion()
            renderOffer(requireNotNull(monthlyPlan), activePromotion)
            loadInvitationSummary()
            renderWebsiteRecharge()
        }.onFailure {
            val fallbackPlan = VipPlan(
                id = MONTHLY_PLAN_ID,
                name = getString(R.string.xingsui_plan_month),
                durationDays = 30,
                originalPriceCents = 2880,
                salePriceCents = 1800,
            )
            monthlyPlan = fallbackPlan
            activePromotion = null
            renderOffer(fallbackPlan, null)
            renderWebsiteRecharge()
            Snackbar.make(binding.root, R.string.xingsui_api_unavailable, Snackbar.LENGTH_LONG).show()
        }
    }

    private suspend fun loadInvitationSummary() {
        runCatching {
            apiClient.getInvitationSummary()
        }.onSuccess {
            renderInvitationSummary(it)
        }
    }

    private fun renderOffer(plan: VipPlan, promotion: PromotionActivity?) {
        val salePrice = promotion?.promoPriceCents ?: plan.salePriceCents
        val discount = plan.originalPriceCents - salePrice
        binding.originalPrice.text = getString(
            R.string.xingsui_original_price_template,
            formatMoney(plan.originalPriceCents),
        )
        binding.monthlySalePrice.text = getString(
            R.string.xingsui_sale_price_template,
            formatMoney(salePrice),
        )
        binding.discountSummary.text = getString(
            R.string.xingsui_discount_template,
            formatMoney(discount.coerceAtLeast(0)),
        )
        binding.orderAmount.text = getString(R.string.xingsui_amount_template, formatMoney(salePrice))
        binding.countdown.text = formatCountdown(promotion?.endsAt)
    }

    private fun renderWebsiteRecharge() {
        binding.paymentQrHint.setText(R.string.xingsui_website_recharge_hint)
        binding.orderStatus.setText(R.string.xingsui_website_recharge_status)
        binding.submitPaid.setText(R.string.xingsui_go_website_recharge)
    }

    private fun openWebsiteRecharge() {
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(WEBSITE_RECHARGE_URL)))
    }

    private fun renderInvitationSummary(summary: InvitationSummary) {
        withdrawableBalanceCents = summary.withdrawableBalanceCents
        binding.inviteCode.text = getString(R.string.xingsui_invite_code_template, summary.inviteCode)
        binding.inviteStats.text = getString(
            R.string.xingsui_invite_stats_template,
            summary.invitedCount,
            summary.paidInviteCount,
        )
        binding.withdrawBalance.text = getString(
            R.string.xingsui_withdraw_balance_template,
            formatMoney(summary.withdrawableBalanceCents),
        )
        binding.submitAlipayWithdrawal.isEnabled = summary.withdrawableBalanceCents >= INVITE_REWARD_CENTS
    }

    private fun formatCountdown(endsAt: Instant?): String {
        val campaignEndsAt = endsAt ?: Instant.now().plus(Duration.ofDays(3)).plus(Duration.ofHours(8))
        val remaining = Duration.between(Instant.now(), campaignEndsAt).coerceAtLeast(Duration.ZERO)
        return getString(
            R.string.xingsui_offer_countdown,
            remaining.toDays(),
            remaining.minusDays(remaining.toDays()).toHours(),
        )
    }

    private fun formatMoney(cents: Int): String {
        val yuan = cents / 100
        val fen = cents % 100
        return when {
            fen == 0 -> yuan.toString()
            fen % 10 == 0 -> "${yuan}.${fen / 10}"
            else -> String.format(Locale.US, "%d.%02d", yuan, fen)
        }
    }

    private fun copyInviteCode() {
        val clipboard = getSystemService<ClipboardManager>() ?: return
        clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.xingsui_copy_invite), session.inviteCode))
        Snackbar.make(binding.root, R.string.xingsui_invite_copied, Snackbar.LENGTH_LONG).show()
    }

    private suspend fun submitAlipayWithdrawal() {
        val account = binding.alipayAccount.text?.toString()?.trim().orEmpty()
        if (withdrawableBalanceCents < INVITE_REWARD_CENTS) {
            Snackbar.make(binding.root, R.string.xingsui_withdraw_unavailable, Snackbar.LENGTH_LONG).show()
            return
        }
        if (account.length < MIN_ACCOUNT_LENGTH) {
            binding.alipayAccount.error = getString(R.string.xingsui_alipay_account_required)
            return
        }
        binding.submitAlipayWithdrawal.isEnabled = false
        runCatching {
            apiClient.createWithdrawal(
                amountCents = withdrawableBalanceCents,
                accountType = ALIPAY_ACCOUNT_TYPE,
                accountMasked = account,
            )
        }.onSuccess {
            binding.alipayAccount.text?.clear()
            Snackbar.make(binding.root, R.string.xingsui_withdraw_submitted, Snackbar.LENGTH_LONG).show()
            loadInvitationSummary()
        }.onFailure {
            binding.submitAlipayWithdrawal.isEnabled = true
            Snackbar.make(binding.root, R.string.xingsui_withdraw_failed, Snackbar.LENGTH_LONG).show()
        }
    }

    private fun copyWithdrawWechat() {
        val clipboard = getSystemService<ClipboardManager>() ?: return
        clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.xingsui_withdraw_wechat_label), WITHDRAW_WECHAT_ID))
        Snackbar.make(
            binding.root,
            getString(R.string.xingsui_withdraw_wechat_copied, WITHDRAW_WECHAT_ID),
            Snackbar.LENGTH_LONG,
        ).show()
    }

    companion object {
        private const val MONTHLY_PLAN_ID = "plan_month"
        private const val INVITE_REWARD_CENTS = 1000
        private const val MIN_ACCOUNT_LENGTH = 4
        private const val ALIPAY_ACCOUNT_TYPE = "alipay"
        private const val WITHDRAW_WECHAT_ID = "xinsuui"
        private const val WEBSITE_RECHARGE_URL = "https://xingsuico.com/vip"
    }
}
