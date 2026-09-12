package org.amnezia.awg.xingsui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.LinearSmoothScroller
import androidx.recyclerview.widget.PagerSnapHelper
import androidx.recyclerview.widget.RecyclerView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.getSystemService
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.launch
import org.amnezia.awg.R
import org.amnezia.awg.databinding.XingsuiVipActivityBinding
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.model.InvitationSummary

class XingsuiVipActivity : AppCompatActivity() {
    private lateinit var apiClient: XingsuiApiClient
    private lateinit var binding: XingsuiVipActivityBinding
    private lateinit var session: AuthSession
    private lateinit var sessionStore: XingsuiSessionStore
    private var selectedPlanId: String? = null
    private lateinit var planAdapter: XingsuiPlanAdapter
    private val snapHelper = PagerSnapHelper()
    private var invitationCode = ""
    private var withdrawalBusy = false
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
        supportActionBar?.hide()
        applyXingsuiSystemInsets(binding.root)
        binding.backButton.setOnClickListener { finish() }
        selectedPlanId = savedInstanceState?.getString("selected_plan")
        invitationCode = session.inviteCode
        setupCarousel()
        binding.submitPaid.isEnabled = false
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
        binding.inviteCode.text = invitationCode
        binding.retryPlans.setOnClickListener { lifecycleScope.launch { loadPlans() } }
        binding.retryInvitation.setOnClickListener { lifecycleScope.launch { loadInvitationSummary() } }
        binding.toggleWithdrawal.setOnClickListener {
            val expanded = binding.withdrawalForm.visibility != View.VISIBLE
            binding.withdrawalForm.visibility = if (expanded) View.VISIBLE else View.GONE
            binding.toggleWithdrawal.text = if (expanded) "收起提现与帮助  ⌃" else "提现与帮助  ›"
        }
        lifecycleScope.launch { loadCommercialData() }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("selected_plan", selectedPlanId)
        super.onSaveInstanceState(outState)
    }

    private fun setupCarousel() {
        val list = binding.planCarousel
        val manager = LinearLayoutManager(this, RecyclerView.HORIZONTAL, false)
        planAdapter = XingsuiPlanAdapter { index ->
            manager.startSmoothScroll(object : LinearSmoothScroller(this) {
                override fun calculateDtToFit(viewStart: Int, viewEnd: Int, boxStart: Int, boxEnd: Int, snapPreference: Int) =
                    (boxStart + boxEnd) / 2 - (viewStart + viewEnd) / 2
            }.apply { targetPosition = index })
        }
        list.layoutManager = manager
        list.adapter = planAdapter
        list.itemAnimator = null
        list.isNestedScrollingEnabled = false
        // Large type expands the card vertically; the outer page remains scrollable.
        list.layoutParams.height = (370 * resources.displayMetrics.density * resources.configuration.fontScale.coerceAtLeast(1f)).toInt()
        snapHelper.attachToRecyclerView(list)
        list.addOnLayoutChangeListener { _, left, _, right, _, oldLeft, _, oldRight, _ ->
            if (right - left > 0 && right - left != oldRight - oldLeft) {
                list.post {
                    val g = XingsuiCarouselGeometry.forViewport(list.width, resources.displayMetrics.density)
                    planAdapter.geometry = g
                    list.setPadding(g.edgePadding, list.paddingTop, g.edgePadding, list.paddingBottom)
                    planAdapter.notifyDataSetChanged()
                    manager.scrollToPositionWithOffset(planAdapter.selectedIndex, 0)
                }
            }
        }
        list.addOnScrollListener(object : RecyclerView.OnScrollListener() {
            override fun onScrollStateChanged(recyclerView: RecyclerView, newState: Int) {
                binding.submitPaid.isEnabled = false
                if (newState == RecyclerView.SCROLL_STATE_IDLE) {
                    recyclerView.post {
                        if (recyclerView.scrollState != RecyclerView.SCROLL_STATE_IDLE) return@post
                        val view = snapHelper.findSnapView(manager) ?: return@post
                        val distance = snapHelper.calculateDistanceToFinalSnap(manager, view) ?: return@post
                        if (kotlin.math.abs(distance[0]) > 1) {
                            recyclerView.smoothScrollBy(distance[0], 0)
                            return@post
                        }
                        val index = manager.getPosition(view)
                        if (index in planAdapter.plans.indices) selectPlan(index)
                    }
                }
            }
        })
    }

    private fun selectPlan(index: Int) {
        val plan = planAdapter.plans[index]
        selectedPlanId = plan.id
        planAdapter.select(index)
        binding.planPosition.text = "${index + 1} / ${planAdapter.itemCount}  ·  左右滑动选择"
        binding.submitPaid.text = "选择此计划 · ¥${membershipMoney(plan.salePriceCents)}"
        binding.submitPaid.isEnabled = true
    }

    private suspend fun loadCommercialData() {
        // Invitation data is independent of plan availability.
        lifecycleScope.launch { loadInvitationSummary() }
        loadPlans()
    }

    private suspend fun loadPlans() {
        binding.retryPlans.visibility = View.GONE
        binding.submitPaid.isEnabled = false
        binding.planPosition.text = "正在加载套餐"
        runCatching { apiClient.listPlans().filter { it.durationDays > 0 }.sortedBy { it.durationDays } }
            .onSuccess { plans ->
                if (plans.isEmpty()) { showPlanLoadError(); return@onSuccess }
                planAdapter.plans = plans
                val index = plans.indexOfFirst { it.id == selectedPlanId }.coerceAtLeast(0)
                planAdapter.selectedIndex = index
                planAdapter.notifyDataSetChanged()
                (binding.planCarousel.layoutManager as LinearLayoutManager).scrollToPositionWithOffset(index, 0)
                selectPlan(index)
            }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it; showPlanLoadError() }
    }

    private fun showPlanLoadError() {
        binding.planPosition.text = "暂时无法加载套餐"
        binding.retryPlans.visibility = View.VISIBLE
        binding.submitPaid.isEnabled = false
    }

    private suspend fun loadInvitationSummary() {
        binding.retryInvitation.visibility = View.GONE
        binding.invitationStatus.text = "邀请数据加载中"
        runCatching { apiClient.getInvitationSummary() }.onSuccess { renderInvitationSummary(it) }.onFailure {
            if (it is kotlinx.coroutines.CancellationException) throw it
            binding.invitationStatus.text = "暂时无法同步邀请数据"
            binding.retryInvitation.visibility = View.VISIBLE
        }
    }

    private fun openWebsiteRecharge() {
        val plan = planAdapter.plans.firstOrNull { it.id == selectedPlanId } ?: return
        val url = Uri.parse(XingsuiApiClient.activeWebOrigin()).buildUpon().path("/payment")
            .appendQueryParameter("plan_id", plan.id).build()
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, url)) }.onFailure {
            Snackbar.make(binding.root, R.string.xingsui_api_unavailable, Snackbar.LENGTH_LONG).show()
        }
    }

    private fun renderInvitationSummary(summary: InvitationSummary) {
        invitationCode = summary.inviteCode
        withdrawableBalanceCents = summary.withdrawableBalanceCents
        binding.inviteCode.text = invitationCode
        binding.invitedCount.text = summary.invitedCount.toString()
        binding.paidCount.text = summary.paidInviteCount.toString()
        binding.withdrawBalance.text = "¥" + membershipMoney(summary.withdrawableBalanceCents)
        binding.invitationStatus.text = "奖励累计 ¥${membershipMoney(summary.totalRewardCents)}"
        binding.submitAlipayWithdrawal.isEnabled = !withdrawalBusy && summary.withdrawableBalanceCents >= INVITE_REWARD_CENTS
    }

    private fun copyInviteCode() {
        val clipboard = getSystemService<ClipboardManager>() ?: return
        clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.xingsui_copy_invite), invitationCode))
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
        if (withdrawalBusy) return
        withdrawalBusy = true
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
            withdrawableBalanceCents = 0
            binding.withdrawBalance.text = "待更新"
            withdrawalBusy = false
            loadInvitationSummary()
        }.onFailure {
            withdrawalBusy = false
            if (it is kotlinx.coroutines.CancellationException) throw it
            binding.submitAlipayWithdrawal.isEnabled = withdrawableBalanceCents >= INVITE_REWARD_CENTS
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
        private const val INVITE_REWARD_CENTS = 1000
        private const val MIN_ACCOUNT_LENGTH = 4
        private const val ALIPAY_ACCOUNT_TYPE = "alipay"
        private const val WITHDRAW_WECHAT_ID = "xinsuui"
    }
}
