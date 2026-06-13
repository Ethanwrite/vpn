package org.amnezia.awg.xingsui

import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.content.Intent
import android.graphics.Color
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
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.snackbar.Snackbar
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
import org.amnezia.awg.config.Config
import org.amnezia.awg.databinding.XingsuiHomeActivityBinding
import org.amnezia.awg.model.ObservableTunnel
import org.amnezia.awg.util.ErrorMessages
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException
import org.amnezia.awg.xingsui.model.UserAccount
import org.amnezia.awg.xingsui.model.VpnNodeConfig
import org.amnezia.awg.xingsui.model.VpnNodeSummary
import java.io.ByteArrayInputStream
import java.nio.charset.StandardCharsets
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

class XingsuiHomeActivity : AppCompatActivity() {
    private lateinit var binding: XingsuiHomeActivityBinding
    private lateinit var sessionStore: XingsuiSessionStore
    private var apiClient: XingsuiApiClient? = null
    private var account: UserAccount? = null
    private var managedTunnel: ObservableTunnel? = null
    private var isBusy = false
    private var selectedNodeId: String? = null
    private var selectedNodeName: String? = null
    private var pendingTunnelToStart: ObservableTunnel? = null
    private var pulseAnimator: AnimatorSet? = null
    private var spinAnimator: ObjectAnimator? = null
    private var statusMonitorJob: Job? = null
    private var connectWatchdogJob: Job? = null
    private var lastEntitlementCheckAtMs = 0L
    private var connectStartedAtMs = 0L
    private var connectAttemptId = 0L
    private val vpnPermissionLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        val tunnel = pendingTunnelToStart
        pendingTunnelToStart = null
        if (tunnel == null) {
            setBusy(false)
            return@registerForActivityResult
        }
        lifecycleScope.launch { startPreparedTunnel(tunnel) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = XingsuiHomeActivityBinding.inflate(layoutInflater)
        sessionStore = XingsuiSessionStore(this)
        setContentView(binding.root)
        supportActionBar?.hide()

        binding.loginButton.setOnClickListener { startActivity(Intent(this, XingsuiAuthActivity::class.java)) }
        binding.registerButton.setOnClickListener { startActivity(Intent(this, XingsuiAuthActivity::class.java)) }
        binding.vipButton.setOnClickListener { openVipCenter() }
        binding.userCenterButton.setOnClickListener { openVipCenter() }
        binding.refreshButton.setOnClickListener { lifecycleScope.launch { refreshHome() } }
        binding.smartModeSwitch.setOnClickListener {
            val message = if (binding.smartModeSwitch.isChecked) {
                R.string.xingsui_home_smart_mode_enabled
            } else {
                R.string.xingsui_home_smart_mode_disabled
            }
            Snackbar.make(binding.root, message, Snackbar.LENGTH_SHORT).show()
        }
        binding.connectButton.setOnClickListener { lifecycleScope.launch { toggleConnection() } }
        binding.nodeManageButton.setOnClickListener {
            lifecycleScope.launch { showNodePicker() }
        }

        renderSignedOut()
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
        stopConnectWatchdog()
        stopPulse()
        super.onDestroy()
    }

    private suspend fun refreshHome() {
        val session = sessionStore.load()
        if (session == null) {
            apiClient = null
            account = null
            managedTunnel = null
            renderSignedOut()
            return
        }
        apiClient = XingsuiApiClient(accessToken = session.accessToken)
        binding.accountEmail.text = session.email
        setBusy(true, getString(R.string.xingsui_home_syncing))
        runCatching {
            val me = requireNotNull(apiClient).getMe()
            account = me
            managedTunnel = findManagedTunnel()
            me
        }.onSuccess { me ->
            setBusy(false)
            renderAccount(me)
            renderTunnelState(managedTunnel)
        }.onFailure {
            setBusy(false)
            XingsuiCrashReporter.recordException("home-refresh", it)
            if (it.isUnauthorized()) {
                clearExpiredSession()
                return
            }
            Snackbar.make(binding.root, R.string.xingsui_vip_verify_failed, Snackbar.LENGTH_LONG).show()
            renderSessionOffline(session.email)
        }
    }

    private fun renderSignedOut() {
        binding.accountEmail.setText(R.string.xingsui_home_guest)
        binding.vipStatus.setText(R.string.xingsui_home_not_logged_in)
        binding.vipExpiry.setText(R.string.xingsui_home_login_to_sync)
        binding.trafficRemaining.setText(R.string.xingsui_home_trial_hint)
        binding.nodeName.setText(R.string.xingsui_home_auto_node)
        binding.connectionState.setText(R.string.xingsui_home_disconnected)
        binding.connectButton.setText(R.string.xingsui_home_login_connect)
        binding.authActions.visibility = View.VISIBLE
        binding.vipButton.isEnabled = true
        binding.userCenterButton.isEnabled = false
        binding.connectButton.isEnabled = true
        stopPulse()
    }

    private fun renderSessionOffline(email: String) {
        binding.accountEmail.text = email
        binding.vipStatus.setText(R.string.xingsui_home_syncing)
        binding.vipExpiry.setText(R.string.xingsui_vip_verify_failed)
        binding.trafficRemaining.setText(R.string.xingsui_home_login_to_sync)
        binding.authActions.visibility = View.GONE
        binding.userCenterButton.isEnabled = true
        binding.connectButton.isEnabled = true
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
        binding.trafficRemaining.text = getString(
            R.string.xingsui_home_free_remaining,
            formatMegabytes(user.freeTrafficRemainingBytes),
        )
        binding.loginButton.isEnabled = false
        binding.registerButton.isEnabled = false
        binding.authActions.visibility = View.GONE
        binding.userCenterButton.isEnabled = true
    }

    private fun renderTunnelState(tunnel: ObservableTunnel?) {
        val state = tunnel?.state ?: Tunnel.State.DOWN
        val isUp = state == Tunnel.State.UP
        binding.nodeName.text = when {
            tunnel == null && selectedNodeId == null -> getString(R.string.xingsui_home_auto_node)
            selectedNodeName != null -> getString(R.string.xingsui_home_node_template, selectedNodeName!!)
            else -> getString(R.string.xingsui_home_node_template, DISPLAY_NODE_NAME)
        }
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
            connectStartedAtMs = 0L
            stopPulse()
        }
    }

    private suspend fun toggleConnection() {
        val session = sessionStore.load()
        if (session == null) {
            startActivity(Intent(this, XingsuiAuthActivity::class.java))
            return
        }
        val client = apiClient ?: XingsuiApiClient(accessToken = session.accessToken).also { apiClient = it }
        val tunnel = managedTunnel ?: findManagedTunnel()
        if (tunnel?.state == Tunnel.State.UP) {
            setBusy(true, getString(R.string.xingsui_home_disconnecting))
            runCatching {
                withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                    tunnel.setStateAsync(Tunnel.State.DOWN)
                }
            }
                .onSuccess {
                    managedTunnel = tunnel
                    setBusy(false)
                    renderTunnelState(tunnel)
                }
                .onFailure {
                    setBusy(false)
                    XingsuiCrashReporter.recordException("home-disconnect", it)
                    Snackbar.make(binding.root, R.string.xingsui_home_disconnect_failed, Snackbar.LENGTH_LONG).show()
                }
            return
        }

        setBusy(true, getString(R.string.xingsui_home_authorizing))
        runCatching {
            withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                val entitlement = client.authorizeVpn()
                if (!entitlement.allowed) {
                    throw XingsuiVipRequiredException(entitlement.reason)
                }
                val readyTunnel = ensureManagedTunnel(client)
                withContext(Dispatchers.Main.immediate) {
                    binding.connectionState.setText(R.string.xingsui_home_connecting)
                }
                prepareAndStartTunnel(readyTunnel)
                readyTunnel
            }
        }.onSuccess { readyTunnel ->
            if (pendingTunnelToStart == null) {
                managedTunnel = readyTunnel
                setBusy(false)
                renderTunnelState(readyTunnel)
                refreshAccountQuietly(client)
            }
        }.onFailure { error ->
            setBusy(false)
            XingsuiCrashReporter.recordException("home-connect", error)
            if (error.isUnauthorized()) {
                clearExpiredSession()
                renderTunnelState(managedTunnel)
                return@onFailure
            }
            val message = when (error) {
                is XingsuiVipRequiredException -> entitlementMessage(error.message)
                else -> error.message ?: getString(R.string.xingsui_home_connect_failed)
            }
            Snackbar.make(binding.root, message, Snackbar.LENGTH_LONG).show()
            if (message == getString(R.string.xingsui_free_trial_exhausted)) {
                openVipCenter()
            }
            renderTunnelState(managedTunnel)
        }
    }

    private suspend fun prepareAndStartTunnel(tunnel: ObservableTunnel) {
        if (Application.getBackend() is GoBackend) {
            val permissionIntent = GoBackend.VpnService.prepare(this)
            if (permissionIntent != null) {
                pendingTunnelToStart = tunnel
                withContext(Dispatchers.Main.immediate) {
                    binding.connectionState.setText(R.string.xingsui_home_waiting_permission)
                    vpnPermissionLauncher.launch(permissionIntent)
                }
                return
            }
        }
        startPreparedTunnel(tunnel)
    }

    private suspend fun startPreparedTunnel(tunnel: ObservableTunnel) {
        val client = apiClient
        val attemptId = ++connectAttemptId
        runCatching {
            withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                withContext(Dispatchers.Main.immediate) {
                    connectStartedAtMs = System.currentTimeMillis()
                    binding.connectionState.setText(R.string.xingsui_home_connecting)
                    scheduleConnectWatchdog(tunnel, attemptId)
                }
                tunnel.setStateAsync(Tunnel.State.UP)
                tunnel
            }
        }.onSuccess {
            if (attemptId != connectAttemptId) {
                runCatching { it.setStateAsync(Tunnel.State.DOWN) }
                return@onSuccess
            }
            stopConnectWatchdog()
            managedTunnel = it
            setBusy(false)
            renderTunnelState(it)
            if (client != null) refreshAccountQuietly(client)
        }.onFailure { error ->
            if (attemptId != connectAttemptId) return@onFailure
            stopConnectWatchdog()
            connectStartedAtMs = 0L
            setBusy(false)
            XingsuiCrashReporter.recordException("home-start-prepared", error)
            val errorText = ErrorMessages[error]
            val message = getString(R.string.error_up, errorText)
            Snackbar.make(binding.root, message, Snackbar.LENGTH_LONG).show()
            renderTunnelState(managedTunnel)
        }
    }

    private suspend fun refreshAccountQuietly(client: XingsuiApiClient) {
        runCatching { client.getMe() }.onSuccess {
            account = it
            renderAccount(it)
        }.onFailure {
            XingsuiCrashReporter.recordException("home-refresh-account-quiet", it)
            if (it.isUnauthorized()) {
                clearExpiredSession()
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
                            runCatching {
                                val statistics = tunnel.getStatisticsAsync()
                                val latestHandshakeAt = statistics.peers().maxOfOrNull { peer ->
                                    statistics.peer(peer)?.latestHandshakeEpochMillis() ?: 0L
                                } ?: 0L
                                if (latestHandshakeAt > 0L) {
                                    connectStartedAtMs = 0L
                                    tunnel.onConnectionStatusChanged(ObservableTunnel.ConnectionStatus.CONNECTED)
                                } else if (connectStartedAtMs > 0L) {
                                    tunnel.onConnectionStatusChanged(ObservableTunnel.ConnectionStatus.CONNECTING)
                                }
                                Unit
                            }
                            maybeRefreshEntitlement(tunnel)
                            maybeStopHandshakeTimeout(tunnel)
                        }
                    }
                    renderTunnelState(tunnel)
                }.onFailure {
                    XingsuiCrashReporter.recordException("home-status-monitor", it)
                }
                delay(STATUS_POLL_INTERVAL_MS)
            }
        }
    }

    private fun stopStatusMonitor() {
        statusMonitorJob?.cancel()
        statusMonitorJob = null
    }

    private fun scheduleConnectWatchdog(tunnel: ObservableTunnel, attemptId: Long) {
        stopConnectWatchdog()
        connectWatchdogJob = lifecycleScope.launch {
            delay(CONNECTION_OPERATION_TIMEOUT_MS + STATUS_POLL_INTERVAL_MS)
            if (attemptId != connectAttemptId || connectStartedAtMs <= 0L) return@launch
            connectAttemptId++
            connectStartedAtMs = 0L
            XingsuiCrashReporter.recordEvent("home-connect-start-timeout", "Stopping tunnel after backend start timeout")
            setBusy(false)
            binding.connectionState.setText(R.string.xingsui_home_disconnected)
            Snackbar.make(binding.root, R.string.xingsui_home_connect_timeout, Snackbar.LENGTH_LONG).show()
            runCatching {
                withTimeout(CONNECTION_OPERATION_TIMEOUT_MS) {
                    tunnel.setStateAsync(Tunnel.State.DOWN)
                }
            }.onFailure {
                XingsuiCrashReporter.recordException("home-connect-start-timeout-stop", it)
            }
            renderTunnelState(tunnel)
        }
    }

    private fun stopConnectWatchdog() {
        connectWatchdogJob?.cancel()
        connectWatchdogJob = null
    }

    private suspend fun maybeRefreshEntitlement(tunnel: ObservableTunnel) {
        val now = System.currentTimeMillis()
        if (now - lastEntitlementCheckAtMs < ENTITLEMENT_CHECK_INTERVAL_MS) return
        lastEntitlementCheckAtMs = now
        val session = sessionStore.load() ?: return
        val client = apiClient ?: XingsuiApiClient(accessToken = session.accessToken).also { apiClient = it }
        val entitlement = try {
            client.authorizeVpn()
        } catch (error: Throwable) {
            if (error.isUnauthorized()) {
                tunnel.setStateAsync(Tunnel.State.DOWN)
                clearExpiredSession()
            }
            throw error
        }
        if (!entitlement.allowed) {
            tunnel.setStateAsync(Tunnel.State.DOWN)
            Snackbar.make(binding.root, entitlementMessage(entitlement.reason), Snackbar.LENGTH_LONG).show()
        }
    }

    private suspend fun maybeStopHandshakeTimeout(tunnel: ObservableTunnel) {
        if (tunnel.state != Tunnel.State.UP) return
        val startedAt = connectStartedAtMs
        if (startedAt <= 0L) return
        if (System.currentTimeMillis() - startedAt < HANDSHAKE_TIMEOUT_MS) return
        stopConnectWatchdog()
        connectStartedAtMs = 0L
        XingsuiCrashReporter.recordEvent("home-handshake-timeout", "Stopping tunnel and rotating config after handshake timeout")
        runCatching {
            tunnel.setStateAsync(Tunnel.State.DOWN)
        }.onFailure {
            XingsuiCrashReporter.recordException("home-handshake-timeout-stop", it)
        }

        val client = apiClient ?: sessionStore.load()?.let {
            XingsuiApiClient(accessToken = it.accessToken).also { createdClient -> apiClient = createdClient }
        }
        if (client == null) {
            Snackbar.make(binding.root, R.string.xingsui_home_connect_timeout, Snackbar.LENGTH_LONG).show()
            renderTunnelState(tunnel)
            return
        }

        runCatching {
            val node = client.getDefaultVpnConfig(rotate = true)
            updateManagedTunnel(tunnel, node)
            managedTunnel = tunnel
            binding.nodeName.text = getString(R.string.xingsui_home_node_template, node.name)
            Snackbar.make(binding.root, R.string.xingsui_home_config_refreshed, Snackbar.LENGTH_LONG).show()
        }.onFailure {
            XingsuiCrashReporter.recordException("home-handshake-timeout-rotate", it)
            Snackbar.make(binding.root, R.string.xingsui_home_connect_timeout, Snackbar.LENGTH_LONG).show()
        }
        renderTunnelState(tunnel)
    }

    private fun clearExpiredSession() {
        sessionStore.clear()
        apiClient = null
        account = null
        Snackbar.make(binding.root, R.string.xingsui_session_expired, Snackbar.LENGTH_LONG).show()
        renderSignedOut()
    }

    private fun Throwable.isUnauthorized(): Boolean =
        (this as? XingsuiHttpException)?.isUnauthorized == true ||
            (cause as? XingsuiHttpException)?.isUnauthorized == true

    private suspend fun ensureManagedTunnel(client: XingsuiApiClient): ObservableTunnel {
        val node = if (selectedNodeId != null) {
            runCatching { client.getNodeConfig(selectedNodeId!!) }
                .getOrElse { client.getDefaultVpnConfig() }
        } else {
            client.getDefaultVpnConfig()
        }
        findManagedTunnel()?.let { existing ->
            updateManagedTunnel(existing, node)
            managedTunnel = existing
            withContext(Dispatchers.Main.immediate) {
                binding.nodeName.text = getString(R.string.xingsui_home_node_template, node.name)
            }
            return existing
        }
        return createManagedTunnel(node).also {
            managedTunnel = it
            withContext(Dispatchers.Main.immediate) {
                binding.nodeName.text = getString(R.string.xingsui_home_node_template, node.name)
            }
        }
    }

    private suspend fun showNodePicker() {
        val client = apiClient ?: run {
            Snackbar.make(binding.root, R.string.xingsui_home_connect_failed, Snackbar.LENGTH_SHORT).show()
            return
        }
        val dialog = BottomSheetDialog(this)
        val dp = resources.displayMetrics.density

        // Root scroll view
        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((16 * dp).toInt(), (12 * dp).toInt(), (16 * dp).toInt(), (24 * dp).toInt())
        }
        scroll.addView(root)

        // Title
        root.addView(TextView(this).apply {
            text = "选择线路"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            typeface = android.graphics.Typeface.DEFAULT_BOLD
            setPadding(0, 0, 0, (14 * dp).toInt())
        })

        // Loading indicator
        val spinner = ProgressBar(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.gravity = Gravity.CENTER_HORIZONTAL }
        }
        root.addView(spinner)

        dialog.setContentView(scroll)
        dialog.show()

        // Load nodes in background
        val nodes = runCatching {
            withContext(Dispatchers.IO) { client.listNodes() }
        }.getOrNull()

        root.removeView(spinner)

        if (nodes == null || nodes.isEmpty()) {
            root.addView(TextView(this).apply {
                text = "暂无可用线路，请稍后重试"
                setTextColor(0xFF7a9bb5.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            })
            return
        }

        // "Auto" row
        root.addView(buildNodeRow(
            dp = dp,
            label = "自动（智能线路）",
            sublabel = "由后端自动选择最优节点",
            isOnline = true,
            isVipOnly = false,
            isLocked = false,
            isSelected = selectedNodeId == null,
            onClick = {
                selectedNodeId = null
                selectedNodeName = null
                binding.nodeName.setText(R.string.xingsui_home_auto_node)
                dialog.dismiss()
            }
        ))

        // Node rows
        nodes.forEach { node ->
            root.addView(buildNodeRow(
                dp = dp,
                label = node.name,
                sublabel = "${node.region}  ${if (node.vipOnly) "· VIP 专属" else ""}",
                isOnline = node.status == "online",
                isVipOnly = node.vipOnly,
                isLocked = node.locked,
                isSelected = selectedNodeId == node.id,
                onClick = {
                    if (!node.locked) {
                        selectedNodeId = node.id
                        selectedNodeName = node.name
                        binding.nodeName.text = getString(R.string.xingsui_home_node_template, node.name)
                        dialog.dismiss()
                    } else {
                        Snackbar.make(binding.root, R.string.xingsui_vip_required_active, Snackbar.LENGTH_SHORT).show()
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
        isVipOnly: Boolean,
        isLocked: Boolean,
        isSelected: Boolean,
        onClick: () -> Unit,
    ): LinearLayout {
        val rowBg = GradientDrawable().apply {
            cornerRadius = (8 * dp)
            setColor(if (isSelected) 0x1520e6d2.toInt() else Color.TRANSPARENT)
        }
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = rowBg
            setPadding((12 * dp).toInt(), (11 * dp).toInt(), (12 * dp).toInt(), (11 * dp).toInt())
            alpha = if (isLocked && !isSelected) 0.55f else 1f
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = (4 * dp).toInt() }
        }

        // Status dot
        val dotColor = when {
            isOnline -> 0xFF4ade80.toInt()
            else -> 0xFF2d4a63.toInt()
        }
        val dot = View(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(dotColor) }
            layoutParams = LinearLayout.LayoutParams((9 * dp).toInt(), (9 * dp).toInt()).also {
                it.marginEnd = (10 * dp).toInt()
            }
        }
        row.addView(dot)

        // Text block
        val textCol = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        textCol.addView(TextView(this).apply {
            text = label
            setTextColor(if (isLocked) 0xFF7a9bb5.toInt() else Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
        })
        if (sublabel.isNotBlank()) {
            textCol.addView(TextView(this).apply {
                text = sublabel.trim()
                setTextColor(0xFF7a9bb5.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            })
        }
        row.addView(textCol)

        // Right badge
        val badge = when {
            isSelected -> "✓"
            isLocked -> "🔒"
            isVipOnly -> "VIP"
            else -> ""
        }
        if (badge.isNotEmpty()) {
            row.addView(TextView(this).apply {
                text = badge
                setTextColor(if (isSelected) 0xFF20e6d2.toInt() else 0xFF7a9bb5.toInt())
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
                setPadding((8 * dp).toInt(), 0, 0, 0)
            })
        }
        return row
    }

    private suspend fun findManagedTunnel(): ObservableTunnel? {
        val tunnels = Application.getTunnelManager().getTunnels()
        return tunnels.firstOrNull { it.name == MANAGED_TUNNEL_NAME }
    }

    private suspend fun createManagedTunnel(node: VpnNodeConfig): ObservableTunnel {
        val config = parseNodeConfig(node)
        val name = node.tunnelName.takeIf { it.matches(TUNNEL_NAME_PATTERN) } ?: MANAGED_TUNNEL_NAME
        return runCatching {
            Application.getTunnelManager().create(name, config)
        }.getOrElse {
            findManagedTunnel() ?: throw it
        }
    }

    private suspend fun updateManagedTunnel(tunnel: ObservableTunnel, node: VpnNodeConfig) {
        tunnel.setConfigAsync(parseNodeConfig(node))
    }

    private suspend fun parseNodeConfig(node: VpnNodeConfig): Config {
        val config = withContext(Dispatchers.IO) {
            ByteArrayInputStream(node.configText.toByteArray(StandardCharsets.UTF_8)).use { Config.parse(it) }
        }
        return config
    }

    private fun setBusy(busy: Boolean, status: String? = null) {
        isBusy = busy
        binding.connectButton.isEnabled = !busy
        binding.refreshButton.isEnabled = !busy
        binding.vipButton.isEnabled = !busy
        binding.userCenterButton.isEnabled = !busy
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

    private fun entitlementMessage(reason: String?): String = when (reason) {
        REASON_FREE_TRAFFIC_EXHAUSTED -> getString(R.string.xingsui_free_trial_exhausted)
        REASON_VIP_EXPIRED -> getString(R.string.xingsui_vip_expired)
        else -> getString(R.string.xingsui_vip_required_active)
    }

    private fun openVipCenter() {
        startActivity(Intent(this, XingsuiVipActivity::class.java))
    }

    private fun formatMegabytes(bytes: Long): String {
        return String.format(Locale.US, "%.1f", bytes.coerceAtLeast(0L) / 1024.0 / 1024.0)
    }

    companion object {
        private const val MANAGED_TUNNEL_NAME = "xingsui"
        private const val DISPLAY_NODE_NAME = "星隧智能节点"
        private const val VIP_ACTIVE = "active"
        private const val VIP_EXPIRED = "expired"
        private const val REASON_FREE_TRAFFIC_EXHAUSTED = "free_traffic_exhausted"
        private const val REASON_VIP_EXPIRED = "vip_expired"
        private const val CONNECTION_OPERATION_TIMEOUT_MS = 30_000L
        private const val HANDSHAKE_TIMEOUT_MS = 25_000L
        private const val STATUS_POLL_INTERVAL_MS = 5_000L
        private const val ENTITLEMENT_CHECK_INTERVAL_MS = 30_000L
        private val TUNNEL_NAME_PATTERN = Regex("[a-zA-Z0-9_=+.-]{1,15}")
        private val DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
    }
}
