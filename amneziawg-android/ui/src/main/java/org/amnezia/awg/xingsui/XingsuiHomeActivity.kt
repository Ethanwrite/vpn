package org.amnezia.awg.xingsui

import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.app.Activity
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.LinearInterpolator
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.amnezia.awg.Application
import org.amnezia.awg.R
import org.amnezia.awg.backend.GoBackend
import org.amnezia.awg.backend.Tunnel
import org.amnezia.awg.databinding.XingsuiHomeActivityBinding
import org.amnezia.awg.model.ObservableTunnel
import org.amnezia.awg.model.TunnelManager
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException
import org.amnezia.awg.xingsui.model.UserAccount
import org.amnezia.awg.xingsui.model.VpnNodeSummary
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class XingsuiHomeActivity : AppCompatActivity() {
    private lateinit var binding: XingsuiHomeActivityBinding
    private lateinit var sessionStore: XingsuiSessionStore
    private var apiClient: XingsuiApiClient? = null
    private var account: UserAccount? = null
    private var managedTunnel: ObservableTunnel? = null
    private var isBusy = false
    private var selectedNodeId: String? = null
    private var selectedNodeName: String? = null
    private var selectedNodeDetail: String? = null
    private var pendingConnectAfterPermission = false
    private var pulseAnimator: AnimatorSet? = null
    private var spinAnimator: ObjectAnimator? = null
    private var statusMonitorJob: Job? = null
    private var connectAttemptId = 0L
    private val vpnPermissionLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (!pendingConnectAfterPermission) {
            setBusy(false)
            return@registerForActivityResult
        }
        pendingConnectAfterPermission = false
        lifecycleScope.launch {
            if (result.resultCode != Activity.RESULT_OK) {
                stopAndDeleteManagedTunnel()
                setBusy(false)
                showConnectionSyncFailure()
                return@launch
            }
            connectWithFreshManagedConfig()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = XingsuiHomeActivityBinding.inflate(layoutInflater)
        sessionStore = XingsuiSessionStore(this)
        setContentView(binding.root)
        supportActionBar?.hide()

        binding.loginButton.setOnClickListener { startActivity(Intent(this, XingsuiAuthActivity::class.java)) }
        binding.registerButton.setOnClickListener { startActivity(Intent(this, XingsuiAuthActivity::class.java)) }
        binding.accountCard.setOnClickListener { openProfile() }
        binding.vipButton.setOnClickListener { openVipCenter() }
        binding.refreshButton.setOnClickListener { lifecycleScope.launch { refreshHome() } }
        binding.smartModeSwitch.setOnClickListener {
            val message = when {
                binding.smartModeSwitch.isChecked -> {
                    selectedNodeId = null
                    selectedNodeName = null
                    selectedNodeDetail = null
                    renderSelectedNode(
                        getString(R.string.xingsui_node_auto_title),
                        getString(R.string.xingsui_node_auto_detail),
                    )
                    R.string.xingsui_home_smart_mode_enabled
                }
                selectedNodeId == null -> {
                    binding.smartModeSwitch.isChecked = true
                    R.string.xingsui_home_select_manual_node
                }
                else -> R.string.xingsui_home_smart_mode_disabled
            }
            Snackbar.make(binding.root, message, Snackbar.LENGTH_SHORT).show()
        }
        binding.connectButton.setOnClickListener { lifecycleScope.launch { toggleConnection() } }
        binding.nodeManageButton.setOnClickListener {
            lifecycleScope.launch { showNodePicker() }
        }

        collectManagedTunnelEvents()
        renderSignedOut()
    }

    /** 展示 TunnelManager 主动断开/自动切换线路的原因，避免静默断开。 */
    private fun collectManagedTunnelEvents() {
        lifecycleScope.launch {
            Application.getTunnelManager().managedTunnelEvents.collect { event ->
                if (!lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) return@collect
                when (event) {
                    is TunnelManager.ManagedTunnelEvent.DeadLinkSwitching ->
                        Snackbar.make(binding.root, R.string.xingsui_link_switching, Snackbar.LENGTH_LONG).show()
                    is TunnelManager.ManagedTunnelEvent.DeadLinkSwitched -> {
                        Snackbar.make(binding.root, R.string.xingsui_link_switched, Snackbar.LENGTH_LONG).show()
                        renderTunnelState(findManagedTunnel())
                    }
                    is TunnelManager.ManagedTunnelEvent.DeadLinkDisconnected -> {
                        Snackbar.make(binding.root, R.string.xingsui_link_dead_disconnected, Snackbar.LENGTH_LONG).show()
                        renderTunnelState(null)
                    }
                    is TunnelManager.ManagedTunnelEvent.EntitlementDenied -> {
                        renderTunnelState(null)
                        showEntitlementRequired(event.reason)
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        startStatusMonitor()
        lifecycleScope.launch { refreshHome() }
    }

    override fun onPause() {
        stopStatusMonitor()
        super.onPause()
    }

    override fun onDestroy() {
        stopStatusMonitor()
        stopPulse()
        super.onDestroy()
    }

    private suspend fun refreshHome() {
        val session = sessionStore.load()
        if (session == null) {
            stopAndDeleteManagedTunnel()
            apiClient = null
            account = null
            renderSignedOut()
            return
        }
        apiClient = XingsuiApiClient(accessToken = session.accessToken)
        binding.accountEmail.text = session.email
        setBusy(true, getString(R.string.xingsui_home_syncing))
        runCatching {
            val me = requireNotNull(apiClient).getMe()
            account = me
            // START_STICKY can briefly leave a DOWN placeholder while TunnelManager is
            // fetching a fresh lease. Never delete it from an observational UI refresh;
            // restoreState owns recovery and explicit disconnect owns removal.
            Application.getTunnelManager().restoreState(true)
            managedTunnel = findManagedTunnel()
            me
        }.onSuccess { me ->
            setBusy(false)
            renderAccount(me)
            renderTunnelState(managedTunnel)
        }.onFailure {
            if (it is CancellationException) throw it
            setBusy(false)
            XingsuiCrashReporter.recordException("home-refresh", it)
            if (it.isUnauthorized()) {
                clearExpiredSession()
                return
            }
            account = null
            managedTunnel = findManagedTunnel()
            Snackbar.make(binding.root, R.string.xingsui_account_sync_failed, Snackbar.LENGTH_LONG).show()
            renderSessionOffline(session.email)
        }
    }

    private fun renderSignedOut() {
        binding.accountEmail.setText(R.string.xingsui_home_guest)
        binding.vipStatus.setText(R.string.xingsui_home_not_logged_in)
        binding.vipExpiry.setText(R.string.xingsui_home_login_to_sync)
        binding.trafficRemaining.setText(R.string.xingsui_home_login_to_sync)
        selectedNodeId = null
        selectedNodeName = null
        selectedNodeDetail = null
        binding.smartModeSwitch.isChecked = true
        renderSelectedNode(
            getString(R.string.xingsui_node_auto_title),
            getString(R.string.xingsui_node_auto_detail),
        )
        binding.connectionState.setText(R.string.xingsui_home_disconnected)
        binding.connectButton.setText(R.string.xingsui_home_login_connect)
        binding.authActions.visibility = View.VISIBLE
        binding.vipButton.isEnabled = true
        binding.connectButton.isEnabled = true
        stopPulse()
    }

    private fun renderSessionOffline(email: String) {
        binding.accountEmail.text = email
        binding.vipStatus.setText(R.string.xingsui_home_syncing)
        binding.vipExpiry.setText(R.string.xingsui_account_sync_failed)
        binding.trafficRemaining.setText(R.string.xingsui_home_login_to_sync)
        binding.authActions.visibility = View.GONE
        binding.connectButton.isEnabled = false
        binding.nodeManageButton.isEnabled = false
        binding.smartModeSwitch.isEnabled = false
        renderTunnelState(managedTunnel)
    }

    private fun renderAccount(user: UserAccount) {
        binding.accountEmail.text = user.email
        binding.vipStatus.text = when (user.vipStatus) {
            VIP_ACTIVE -> getString(R.string.xingsui_home_vip_active)
            VIP_EXPIRED -> getString(R.string.xingsui_home_vip_expired)
            else -> getString(R.string.xingsui_home_vip_inactive)
        }
        binding.vipExpiry.text = user.vipExpiredAt?.atZone(ZoneId.systemDefault())?.format(DATE_FORMATTER)
            ?: getString(R.string.xingsui_home_no_expiry)
        binding.trafficRemaining.text = if (user.vipStatus == VIP_ACTIVE) {
            getString(R.string.xingsui_home_traffic_vip)
        } else {
            getString(
                R.string.xingsui_home_traffic_remaining,
                XingsuiTraffic.formatBytes(user.freeTrafficRemainingBytes),
                XingsuiTraffic.formatBytes(user.freeTrafficQuotaBytes),
            )
        }
        binding.loginButton.isEnabled = false
        binding.registerButton.isEnabled = false
        binding.authActions.visibility = View.GONE
        binding.connectButton.isEnabled = true
        binding.nodeManageButton.isEnabled = true
        binding.smartModeSwitch.isEnabled = true
    }

    private fun renderTunnelState(tunnel: ObservableTunnel?) {
        val state = tunnel?.state ?: Tunnel.State.DOWN
        val isUp = state == Tunnel.State.UP
        val nodeTitle = selectedNodeName ?: if (selectedNodeId == null) {
            getString(R.string.xingsui_node_auto_title)
        } else {
            DISPLAY_NODE_NAME
        }
        val nodeDetail = selectedNodeDetail ?: getString(R.string.xingsui_node_auto_detail)
        renderSelectedNode(nodeTitle, nodeDetail)
        binding.connectionState.text = when {
            isBusy -> binding.connectionState.text
            isUp && tunnel?.connectionStatus == ObservableTunnel.ConnectionStatus.CONNECTED -> getString(R.string.xingsui_home_connected)
            isUp -> getString(R.string.xingsui_home_connecting)
            else -> getString(R.string.xingsui_home_disconnected)
        }
        binding.connectButton.text = if (isUp) {
            getString(R.string.xingsui_home_disconnect)
        } else {
            getString(R.string.xingsui_home_connect)
        }
        if (isUp && tunnel?.connectionStatus == ObservableTunnel.ConnectionStatus.CONNECTED) {
            stopSpin()
            startPulse()
        } else if (isUp) {
            startConnectingAnimation()
        } else if (!isBusy) {
            stopPulse()
        }
    }

    private suspend fun toggleConnection() {
        if (sessionStore.load() == null) {
            startActivity(Intent(this, XingsuiAuthActivity::class.java))
            return
        }
        val tunnel = managedTunnel ?: findManagedTunnel()
        if (tunnel?.state == Tunnel.State.UP) {
            setBusy(true, getString(R.string.xingsui_home_disconnecting))
            runCatching {
                withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                    tunnel.setStateAsync(Tunnel.State.DOWN)
                }
            }
                .onSuccess {
                    runCatching { tunnel.deleteAsync() }
                        .onFailure { XingsuiCrashReporter.recordException("home-disconnect-delete-config", it) }
                    managedTunnel = null
                    setBusy(false)
                    renderTunnelState(null)
                }
                .onFailure {
                    XingsuiCrashReporter.recordException("home-disconnect", it)
                    stopAndDeleteManagedTunnel(tunnel)
                    setBusy(false)
                    showConnectionSyncFailure()
                }
            return
        }

        setBusy(true, getString(R.string.xingsui_home_authorizing))
        runCatching { prepareVpnPermissionOrConnect() }
            .onFailure {
                if (it is CancellationException && it !is TimeoutCancellationException) throw it
                XingsuiCrashReporter.recordException("home-permission-prepare", it)
                stopAndDeleteManagedTunnel()
                setBusy(false)
                renderTunnelState(null)
                showConnectionSyncFailure()
            }
    }

    private suspend fun prepareVpnPermissionOrConnect() {
        if (Application.getBackend() is GoBackend) {
            val permissionIntent = GoBackend.VpnService.prepare(this)
            if (permissionIntent != null) {
                pendingConnectAfterPermission = true
                withContext(Dispatchers.Main.immediate) {
                    binding.connectionState.setText(R.string.xingsui_home_waiting_permission)
                    vpnPermissionLauncher.launch(permissionIntent)
                }
                return
            }
        }
        connectWithFreshManagedConfig()
    }

    private suspend fun connectWithFreshManagedConfig() {
        val attemptId = ++connectAttemptId
        runCatching {
            withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                withContext(Dispatchers.Main.immediate) {
                    binding.connectionState.setText(R.string.xingsui_home_connecting)
                }
                Application.getTunnelManager().connectManagedTunnel(selectedNodeId)
            }
        }.onSuccess {
            if (attemptId != connectAttemptId) {
                runCatching { it.setStateAsync(Tunnel.State.DOWN) }
                return@onSuccess
            }
            managedTunnel = it
            setBusy(false)
            renderTunnelState(it)
        }.onFailure { error ->
            if (error is CancellationException && error !is TimeoutCancellationException) throw error
            if (attemptId != connectAttemptId) return@onFailure
            setBusy(false)
            XingsuiCrashReporter.recordException("home-start-prepared", error)
            stopAndDeleteManagedTunnel()
            renderTunnelState(null)
            if (error is XingsuiEntitlementException) {
                showEntitlementRequired(error.reason)
            } else {
                showConnectionSyncFailure()
            }
        }
    }

    private fun startStatusMonitor() {
        if (statusMonitorJob?.isActive == true) return
        statusMonitorJob = lifecycleScope.launch {
            while (isActive) {
                runCatching {
                    val tunnel = findManagedTunnel()
                    managedTunnel = tunnel
                    if (tunnel != null) {
                        Application.getTunnelManager().getTunnelState(tunnel)
                        if (tunnel.state == Tunnel.State.UP) {
                            check(sessionStore.load() != null) { "missing_session" }
                            val statistics = tunnel.getStatisticsAsync()
                            val latestHandshakeAt = statistics.peers().maxOfOrNull { peer ->
                                statistics.peer(peer)?.latestHandshakeEpochMillis() ?: 0L
                            } ?: 0L
                            if (latestHandshakeAt > 0L) {
                                tunnel.onConnectionStatusChanged(ObservableTunnel.ConnectionStatus.CONNECTED)
                            } else {
                                tunnel.onConnectionStatusChanged(ObservableTunnel.ConnectionStatus.CONNECTING)
                            }
                        }
                    }
                    renderTunnelState(tunnel)
                }.onFailure {
                    XingsuiCrashReporter.recordException("home-status-monitor", it)
                    // A status/statistics read can fail while Android is changing networks
                    // or waking from Doze. It is observational, never authority to disconnect.
                    renderTunnelState(managedTunnel)
                }
                delay(STATUS_POLL_INTERVAL_MS)
            }
        }
    }

    private fun stopStatusMonitor() {
        statusMonitorJob?.cancel()
        statusMonitorJob = null
    }

    private suspend fun clearExpiredSession() {
        stopAndDeleteManagedTunnel()
        sessionStore.clear()
        apiClient = null
        account = null
        showConnectionSyncFailure()
        renderSignedOut()
    }

    private fun Throwable.isUnauthorized(): Boolean =
        (this as? XingsuiHttpException)?.isUnauthorized == true ||
            (cause as? XingsuiHttpException)?.isUnauthorized == true

    private suspend fun showNodePicker() {
        val client = apiClient ?: run {
            Snackbar.make(binding.root, R.string.xingsui_home_connect_failed, Snackbar.LENGTH_SHORT).show()
            return
        }
        val dialog = BottomSheetDialog(this)
        val dp = resources.displayMetrics.density
        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            isFillViewport = true
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0xFF1B1829.toInt(), 0xFF0D0D16.toInt()),
            ).apply {
                cornerRadii = floatArrayOf(
                    28 * dp, 28 * dp,
                    28 * dp, 28 * dp,
                    0f, 0f,
                    0f, 0f,
                )
                setStroke((1 * dp).toInt().coerceAtLeast(1), 0xFF343047.toInt())
            }
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((18 * dp).toInt(), (10 * dp).toInt(), (18 * dp).toInt(), (30 * dp).toInt())
        }
        scroll.addView(root)

        root.addView(View(this).apply {
            background = GradientDrawable().apply {
                cornerRadius = 999f
                setColor(0xFF545064.toInt())
            }
            layoutParams = LinearLayout.LayoutParams((42 * dp).toInt(), (4 * dp).toInt()).also {
                it.gravity = Gravity.CENTER_HORIZONTAL
                it.bottomMargin = (18 * dp).toInt()
            }
        })
        root.addView(TextView(this).apply {
            setText(R.string.xingsui_node_picker_title)
            setTextColor(0xFFF7F5FF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 21f)
            typeface = Typeface.DEFAULT_BOLD
        })
        val subtitle = TextView(this).apply {
            setText(R.string.xingsui_node_picker_loading)
            setTextColor(0xFFA7AEC2.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f)
            setPadding(0, (5 * dp).toInt(), 0, (18 * dp).toInt())
        }
        root.addView(subtitle)

        val spinnerBox = LinearLayout(this).apply {
            gravity = Gravity.CENTER
            setPadding(0, (22 * dp).toInt(), 0, (30 * dp).toInt())
        }
        val spinner = ProgressBar(this).apply {
            indeterminateTintList = ColorStateList.valueOf(0xFF8B5CF6.toInt())
            layoutParams = LinearLayout.LayoutParams((34 * dp).toInt(), (34 * dp).toInt())
        }
        spinnerBox.addView(spinner)
        root.addView(spinnerBox)

        dialog.setOnShowListener {
            dialog.findViewById<View>(com.google.android.material.R.id.design_bottom_sheet)?.let { sheet ->
                sheet.setBackgroundColor(Color.TRANSPARENT)
                sheet.elevation = 24 * dp
                BottomSheetBehavior.from(sheet).state = BottomSheetBehavior.STATE_EXPANDED
            }
            dialog.window?.setDimAmount(0.72f)
        }
        dialog.setContentView(scroll)
        dialog.show()

        val nodes = runCatching {
            withContext(Dispatchers.IO) { client.listNodes() }
        }.getOrNull()

        root.removeView(spinnerBox)

        if (nodes == null || nodes.isEmpty()) {
            subtitle.setText(R.string.xingsui_node_picker_empty)
            subtitle.setTextColor(0xFFFF9A9A.toInt())
            return
        }

        subtitle.setText(R.string.xingsui_node_picker_count)
        val canonicalSelection = selectedNodeId?.let { selectedId ->
            nodes.firstOrNull { it.id == selectedId && isAndroidNodeSupported(it) }
        }
        if (selectedNodeId != null && canonicalSelection == null) {
            selectedNodeId = null
            selectedNodeName = null
            selectedNodeDetail = null
            binding.smartModeSwitch.isChecked = true
            renderSelectedNode(
                getString(R.string.xingsui_node_auto_title),
                getString(R.string.xingsui_node_auto_detail),
            )
        } else if (canonicalSelection != null) {
            selectedNodeName = canonicalSelection.name
            selectedNodeDetail = nodeDetail(canonicalSelection)
            renderSelectedNode(canonicalSelection.name, requireNotNull(selectedNodeDetail))
        }

        root.addView(buildNodeRow(
            dp = dp,
            label = getString(R.string.xingsui_node_auto_title),
            sublabel = getString(R.string.xingsui_node_auto_detail),
            isOnline = true,
            isLocked = false,
            isSelected = selectedNodeId == null,
            badge = if (selectedNodeId == null) getString(R.string.xingsui_node_selected_badge) else "",
            onClick = {
                selectedNodeId = null
                selectedNodeName = null
                selectedNodeDetail = null
                binding.smartModeSwitch.isChecked = true
                renderSelectedNode(
                    getString(R.string.xingsui_node_auto_title),
                    getString(R.string.xingsui_node_auto_detail),
                )
                dialog.dismiss()
            }
        ))

        nodes.forEach { node ->
            val isSupported = isAndroidNodeSupported(node)
            val isSelected = selectedNodeId == node.id && isSupported
            val isLocked = node.locked || !isSupported
            val badge = when {
                isSelected -> getString(R.string.xingsui_node_selected_badge)
                !isSupported -> getString(R.string.xingsui_node_unavailable_short)
                node.locked && node.vipOnly -> "VIP"
                node.locked -> getString(R.string.xingsui_node_unavailable_short)
                node.status == "online" -> getString(R.string.xingsui_node_choose)
                else -> getString(R.string.xingsui_node_maintenance)
            }
            root.addView(buildNodeRow(
                dp = dp,
                label = node.name,
                sublabel = nodeListDetail(node),
                isOnline = node.status == "online",
                isLocked = isLocked,
                isSelected = isSelected,
                badge = badge,
                onClick = {
                    when {
                        !isSupported -> Snackbar.make(
                            binding.root,
                            R.string.xingsui_node_android_unsupported,
                            Snackbar.LENGTH_LONG,
                        ).show()
                        node.locked && node.vipOnly -> Snackbar.make(
                            binding.root,
                            R.string.xingsui_vip_required_active,
                            Snackbar.LENGTH_SHORT,
                        ).show()
                        node.locked -> Snackbar.make(
                            binding.root,
                            R.string.xingsui_node_unavailable,
                            Snackbar.LENGTH_SHORT,
                        ).show()
                        else -> {
                            selectedNodeId = node.id
                            selectedNodeName = node.name
                            selectedNodeDetail = nodeDetail(node)
                            binding.smartModeSwitch.isChecked = false
                            renderSelectedNode(node.name, requireNotNull(selectedNodeDetail))
                            dialog.dismiss()
                        }
                    }
                }
            ))
        }
    }

    private fun buildNodeRow(
        dp: Float,
        label: String,
        sublabel: String,
        isOnline: Boolean,
        isLocked: Boolean,
        isSelected: Boolean,
        badge: String,
        onClick: () -> Unit,
    ): LinearLayout {
        val rowBg = if (isSelected) {
            GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                intArrayOf(0xFF30265E.toInt(), 0xFF211B43.toInt()),
            ).apply {
                cornerRadius = 16 * dp
                setStroke((2 * dp).toInt().coerceAtLeast(1), 0xFF8B5CF6.toInt())
            }
        } else {
            GradientDrawable().apply {
                cornerRadius = 16 * dp
                setColor(0xFF171720.toInt())
                setStroke((1 * dp).toInt().coerceAtLeast(1), 0xFF302E40.toInt())
            }
        }
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = rowBg
            minimumHeight = (76 * dp).toInt()
            setPadding((15 * dp).toInt(), (13 * dp).toInt(), (14 * dp).toInt(), (13 * dp).toInt())
            alpha = if (isLocked && !isSelected) 0.72f else 1f
            setOnClickListener { onClick() }
            elevation = if (isSelected) 8 * dp else 0f
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = (10 * dp).toInt() }
        }

        val dotColor = if (isOnline) 0xFF34D399.toInt() else 0xFF646579.toInt()
        val dot = View(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(dotColor) }
            layoutParams = LinearLayout.LayoutParams((10 * dp).toInt(), (10 * dp).toInt()).also {
                it.marginEnd = (12 * dp).toInt()
            }
        }
        row.addView(dot)

        val textCol = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        textCol.addView(TextView(this).apply {
            text = label
            setTextColor(if (isLocked) 0xFFC3C4D2.toInt() else 0xFFF8F7FF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            typeface = Typeface.DEFAULT_BOLD
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
        })
        if (sublabel.isNotBlank()) {
            textCol.addView(TextView(this).apply {
                text = sublabel.trim()
                setTextColor(if (isSelected) 0xFFD7D1F8.toInt() else 0xFFA7AEC2.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
                setPadding(0, (5 * dp).toInt(), 0, 0)
                maxLines = 2
            })
        }
        row.addView(textCol)

        if (badge.isNotEmpty()) {
            row.addView(TextView(this).apply {
                text = if (isSelected) "✓  $badge" else badge
                setTextColor(if (isSelected) Color.WHITE else 0xFFC2B9F5.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 11f)
                typeface = Typeface.DEFAULT_BOLD
                gravity = Gravity.CENTER
                background = GradientDrawable().apply {
                    cornerRadius = 999f
                    setColor(if (isSelected) 0xFF7C3AED.toInt() else 0xFF27223D.toInt())
                    setStroke((1 * dp).toInt().coerceAtLeast(1), 0xFF4A416A.toInt())
                }
                setPadding((10 * dp).toInt(), (5 * dp).toInt(), (10 * dp).toInt(), (5 * dp).toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).also { it.marginStart = (10 * dp).toInt() }
            })
        }
        return row
    }

    private fun isAndroidNodeSupported(node: VpnNodeSummary): Boolean =
        node.protocol.equals(PROTOCOL_AMNEZIAWG, ignoreCase = true)

    private fun nodeDetail(node: VpnNodeSummary): String = publicNodeRegion(node.region)

    private fun nodeListDetail(node: VpnNodeSummary): String {
        val status = if (node.status == "online") {
            getString(R.string.xingsui_node_available)
        } else {
            getString(R.string.xingsui_node_maintenance)
        }
        return listOf(publicNodeRegion(node.region), status)
            .filter { it.isNotBlank() }
            .joinToString(" · ")
    }

    private fun publicNodeRegion(region: String): String {
        return region.replace(Regex("\\s*·\\s*大阪中转落地"), "").trim()
    }

    private fun renderSelectedNode(name: String, detail: String) {
        binding.nodeName.text = getString(R.string.xingsui_home_node_template, name)
        binding.nodeDetail.text = detail
    }

    private suspend fun findManagedTunnel(): ObservableTunnel? {
        val tunnels = Application.getTunnelManager().getTunnels()
        return tunnels.firstOrNull { it.name == MANAGED_TUNNEL_NAME }
    }

    private suspend fun stopAndDeleteManagedTunnel(tunnel: ObservableTunnel? = null) {
        val targetTunnel = tunnel ?: managedTunnel ?: findManagedTunnel()
        if (targetTunnel == null) {
            managedTunnel = null
            return
        }
        if (targetTunnel.state == Tunnel.State.UP) {
            runCatching {
                withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                    targetTunnel.setStateAsync(Tunnel.State.DOWN)
                }
            }.onFailure { XingsuiCrashReporter.recordException("home-security-stop", it) }
        }
        runCatching { targetTunnel.deleteAsync() }
            .onFailure { XingsuiCrashReporter.recordException("home-security-delete-config", it) }
        managedTunnel = null
    }

    private fun setBusy(busy: Boolean, status: String? = null) {
        isBusy = busy
        binding.connectButton.isEnabled = !busy
        binding.refreshButton.isEnabled = !busy
        binding.vipButton.isEnabled = !busy
        binding.smartModeSwitch.isEnabled = !busy
        if (status != null) {
            binding.connectionState.text = status
        }
        if (busy) {
            startConnectingAnimation()
        } else if (managedTunnel?.state != Tunnel.State.UP) {
            stopPulse()
        }
    }

    private fun showConnectionSyncFailure() {
        Snackbar.make(binding.root, R.string.xingsui_account_sync_failed, Snackbar.LENGTH_LONG).show()
    }

    private fun showEntitlementRequired(reason: String) {
        val (titleRes, bodyRes) = when (reason) {
            REASON_FREE_TRAFFIC_EXHAUSTED ->
                R.string.xingsui_paywall_free_title to R.string.xingsui_paywall_free_body
            REASON_VIP_EXPIRED ->
                R.string.xingsui_paywall_vip_expired_title to R.string.xingsui_paywall_vip_expired_body
            else ->
                R.string.xingsui_paywall_vip_required_title to R.string.xingsui_paywall_vip_required_body
        }
        showPaywallCard(titleRes, bodyRes)
    }

    /**
     * 免费流量用尽 / 会员到期时的友好提示卡片。样式与节点选择底部卡片保持一致，
     * 只提醒用户前往官网开通会员，**不再自动跳转 App 内充值页**。
     */
    private fun showPaywallCard(titleRes: Int, bodyRes: Int) {
        val dialog = BottomSheetDialog(this)
        val dp = resources.displayMetrics.density
        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
            isFillViewport = true
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0xFF1B1829.toInt(), 0xFF0D0D16.toInt()),
            ).apply {
                cornerRadii = floatArrayOf(28 * dp, 28 * dp, 28 * dp, 28 * dp, 0f, 0f, 0f, 0f)
                setStroke((1 * dp).toInt().coerceAtLeast(1), 0xFF343047.toInt())
            }
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((22 * dp).toInt(), (10 * dp).toInt(), (22 * dp).toInt(), (26 * dp).toInt())
        }
        scroll.addView(root)

        root.addView(View(this).apply {
            background = GradientDrawable().apply {
                cornerRadius = 999f
                setColor(0xFF545064.toInt())
            }
            layoutParams = LinearLayout.LayoutParams((42 * dp).toInt(), (4 * dp).toInt()).also {
                it.gravity = Gravity.CENTER_HORIZONTAL
                it.bottomMargin = (20 * dp).toInt()
            }
        })
        root.addView(TextView(this).apply {
            setText(titleRes)
            setTextColor(0xFFF7F5FF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            typeface = Typeface.DEFAULT_BOLD
        })
        root.addView(TextView(this).apply {
            setText(bodyRes)
            setTextColor(0xFFA7AEC2.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setLineSpacing(6 * dp, 1f)
            setPadding(0, (10 * dp).toInt(), 0, (24 * dp).toInt())
        })
        root.addView(TextView(this).apply {
            setText(R.string.xingsui_paywall_open_website)
            gravity = Gravity.CENTER
            setTextColor(0xFFFFFFFF.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            typeface = Typeface.DEFAULT_BOLD
            background = GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                intArrayOf(0xFF8B5CF6.toInt(), 0xFF6D3FEA.toInt()),
            ).apply { cornerRadius = 16 * dp }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, (52 * dp).toInt(),
            )
            setOnClickListener {
                dialog.dismiss()
                openWebsite()
            }
        })
        root.addView(TextView(this).apply {
            setText(R.string.xingsui_paywall_dismiss)
            gravity = Gravity.CENTER
            setTextColor(0xFF9AA1B8.toInt())
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, (48 * dp).toInt(),
            ).also { it.topMargin = (6 * dp).toInt() }
            setOnClickListener { dialog.dismiss() }
        })

        dialog.setOnShowListener {
            dialog.findViewById<View>(com.google.android.material.R.id.design_bottom_sheet)?.let { sheet ->
                sheet.setBackgroundColor(Color.TRANSPARENT)
                sheet.elevation = 24 * dp
                BottomSheetBehavior.from(sheet).state = BottomSheetBehavior.STATE_EXPANDED
            }
            dialog.window?.setDimAmount(0.72f)
        }
        dialog.setContentView(scroll)
        dialog.show()
    }

    private fun openWebsite() {
        val origin = XingsuiApiClient.activeWebOrigin()
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(origin))) }
            .onFailure { Snackbar.make(binding.root, R.string.xingsui_api_unavailable, Snackbar.LENGTH_LONG).show() }
    }

    private fun startConnectingAnimation() {
        startPulse()
        if (spinAnimator?.isRunning == true) return
        binding.powerRing.rotation = 0f
        spinAnimator = ObjectAnimator.ofFloat(binding.powerRing, View.ROTATION, 0f, 360f).apply {
            duration = 900L
            repeatCount = ObjectAnimator.INFINITE
            interpolator = LinearInterpolator()
            start()
        }
    }

    private fun startPulse() {
        if (pulseAnimator?.isRunning == true) return
        val scaleX = ObjectAnimator.ofFloat(binding.powerRing, View.SCALE_X, 1f, 1.08f, 1f).apply {
            repeatCount = ObjectAnimator.INFINITE
        }
        val scaleY = ObjectAnimator.ofFloat(binding.powerRing, View.SCALE_Y, 1f, 1.08f, 1f).apply {
            repeatCount = ObjectAnimator.INFINITE
        }
        pulseAnimator = AnimatorSet().apply {
            duration = 1200L
            interpolator = AccelerateDecelerateInterpolator()
            playTogether(scaleX, scaleY)
            start()
        }
    }

    private fun stopPulse() {
        pulseAnimator?.cancel()
        pulseAnimator = null
        stopSpin()
        binding.powerRing.scaleX = 1f
        binding.powerRing.scaleY = 1f
    }

    private fun stopSpin() {
        spinAnimator?.cancel()
        spinAnimator = null
        binding.powerRing.rotation = 0f
    }

    private fun openVipCenter() {
        startActivity(Intent(this, XingsuiVipActivity::class.java))
    }

    private fun openProfile() {
        val destination = if (sessionStore.load() == null) {
            XingsuiAuthActivity::class.java
        } else {
            XingsuiProfileActivity::class.java
        }
        startActivity(Intent(this, destination))
    }

    companion object {
        private const val MANAGED_TUNNEL_NAME = "xingsui"
        private const val DISPLAY_NODE_NAME = "星隧智能节点"
        private const val PROTOCOL_AMNEZIAWG = "amneziawg"
        private const val VIP_ACTIVE = "active"
        private const val VIP_EXPIRED = "expired"
        private const val REASON_FREE_TRAFFIC_EXHAUSTED = "free_traffic_exhausted"
        private const val REASON_VIP_EXPIRED = "vip_expired"
        private const val CONNECTION_OPERATION_TIMEOUT_MS = 30_000L
        private const val STATUS_POLL_INTERVAL_MS = 5_000L
        private val DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
    }
}
