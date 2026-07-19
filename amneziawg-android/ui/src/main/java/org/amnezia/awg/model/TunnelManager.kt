/*
 * Copyright © 2017-2023 WireGuard LLC. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */
package org.amnezia.awg.model

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import android.widget.Toast
import androidx.databinding.BaseObservable
import androidx.databinding.Bindable
import org.amnezia.awg.Application.Companion.get
import org.amnezia.awg.Application.Companion.getBackend
import org.amnezia.awg.Application.Companion.getTunnelManager
import org.amnezia.awg.BR
import org.amnezia.awg.R
import org.amnezia.awg.backend.Statistics
import org.amnezia.awg.backend.StatusCallback
import org.amnezia.awg.backend.Tunnel
import org.amnezia.awg.backend.GoBackend
import org.amnezia.awg.configStore.ConfigStore
import org.amnezia.awg.databinding.ObservableSortedKeyedArrayList
import org.amnezia.awg.util.ErrorMessages
import org.amnezia.awg.util.UserKnobs
import org.amnezia.awg.util.applicationScope
import org.amnezia.awg.config.Config
import org.amnezia.awg.xingsui.XingsuiSessionStore
import org.amnezia.awg.xingsui.XingsuiConnectionSyncException
import org.amnezia.awg.xingsui.XingsuiEntitlementException
import org.amnezia.awg.xingsui.XingsuiCrashReporter
import org.amnezia.awg.xingsui.XingsuiVipGate
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.Instant

/**
 * Maintains and mediates changes to the set of available AmneziaWG tunnels,
 */
class TunnelManager(private val configStore: ConfigStore) : BaseObservable() {
    private val tunnels = CompletableDeferred<ObservableSortedKeyedArrayList<String, ObservableTunnel>>()
    private val context: Context = get()
    private val tunnelMap: ObservableSortedKeyedArrayList<String, ObservableTunnel> = ObservableSortedKeyedArrayList(TunnelComparator)
    private val usageReporterJobs = mutableMapOf<String, Job>()
    private var managedLeaseExpiryJob: Job? = null
    private var managedNodeId: String? = null
    private var managedServedNodeId: String? = null
    private var managedLeaseId: String? = null
    private var autoSwitchAttempts = 0
    private var haveLoaded = false

    /** UI-facing notifications for managed-tunnel teardowns that the user didn't initiate. */
    sealed class ManagedTunnelEvent {
        object DeadLinkSwitching : ManagedTunnelEvent()
        object DeadLinkSwitched : ManagedTunnelEvent()
        object DeadLinkDisconnected : ManagedTunnelEvent()
        object ReportFailureDisconnected : ManagedTunnelEvent()
        data class EntitlementDenied(val reason: String) : ManagedTunnelEvent()
    }

    private val managedTunnelEventsFlow = MutableSharedFlow<ManagedTunnelEvent>(extraBufferCapacity = 16)
    val managedTunnelEvents: SharedFlow<ManagedTunnelEvent> = managedTunnelEventsFlow.asSharedFlow()

    private fun addToList(name: String, config: Config?, state: Tunnel.State): ObservableTunnel {
        val tunnel = ObservableTunnel(this, name, config, state)
        tunnelMap.add(tunnel)
        return tunnel
    }

    suspend fun getTunnels(): ObservableSortedKeyedArrayList<String, ObservableTunnel> = tunnels.await()

    suspend fun create(name: String, config: Config?): ObservableTunnel = withContext(Dispatchers.Main.immediate) {
        if (Tunnel.isNameInvalid(name))
            throw IllegalArgumentException(context.getString(R.string.tunnel_error_invalid_name))
        if (tunnelMap.containsKey(name))
            throw IllegalArgumentException(context.getString(R.string.tunnel_error_already_exists, name))
        addToList(name, withContext(Dispatchers.IO) { configStore.create(name, config!!) }, Tunnel.State.DOWN)
    }

    suspend fun connectManagedTunnel(nodeId: String? = null): ObservableTunnel {
        autoSwitchAttempts = 0
        return connectManagedTunnelInternal(nodeId = nodeId, stopExistingFirst = false)
    }

    suspend fun reconnectManagedTunnel(tunnel: ObservableTunnel): ObservableTunnel {
        require(tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME)
        autoSwitchAttempts = 0
        return connectManagedTunnelInternal(nodeId = managedNodeId, stopExistingFirst = true)
    }

    private suspend fun connectManagedTunnelInternal(
        nodeId: String?,
        stopExistingFirst: Boolean,
        excludeNodeId: String? = null,
    ): ObservableTunnel = withContext(Dispatchers.Main.immediate) {
        var target = tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME]
        try {
            val backend = getBackend()
            if (backend is GoBackend && GoBackend.VpnService.prepare(context) != null) {
                throw XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
            }

            if (stopExistingFirst && target != null) {
                stopManagedTunnelBackend(target)
            }

            val fresh = XingsuiVipGate.requireFreshManagedConfig(context, nodeId, excludeNodeId)
            val managedTunnel = target?.also { existing ->
                existing.onConfigChanged(withContext(Dispatchers.IO) {
                    configStore.save(XINGSUI_MANAGED_TUNNEL_NAME, fresh.config)
                })
            } ?: addToList(
                XINGSUI_MANAGED_TUNNEL_NAME,
                withContext(Dispatchers.IO) {
                    configStore.create(XINGSUI_MANAGED_TUNNEL_NAME, fresh.config)
                },
                Tunnel.State.DOWN,
            )
            target = managedTunnel

            val newState = withContext(Dispatchers.IO) {
                backend.setState(managedTunnel, Tunnel.State.UP, fresh.config)
            }
            managedTunnel.onStateChanged(newState)
            check(newState == Tunnel.State.UP) { "managed_tunnel_not_started" }
            lastUsedTunnel = managedTunnel
            saveState()
            managedNodeId = nodeId
            managedServedNodeId = fresh.response.id
            managedLeaseId = fresh.response.leaseId
            scheduleManagedLeaseExpiry(managedTunnel, fresh.response.expiresAt)
            startUsageReporter(managedTunnel)
            managedTunnel
        } catch (error: Throwable) {
            securelyRemoveManagedTunnel(target)
            if (error is CancellationException) throw error
            XingsuiCrashReporter.recordEvent(
                "managed-tunnel-start-failed",
                error.javaClass.simpleName.ifBlank { "unknown" },
            )
            throw when (error) {
                is XingsuiEntitlementException -> error
                is XingsuiConnectionSyncException -> error
                else -> XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
            }
        }
    }

    private suspend fun stopManagedTunnelBackend(tunnel: ObservableTunnel) {
        stopUsageReporter(tunnel.name)
        managedLeaseExpiryJob?.cancel()
        managedLeaseExpiryJob = null
        runCatching {
            withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.DOWN, null) }
        }.onFailure {
            XingsuiCrashReporter.recordEvent("managed-tunnel-stop-failed", it.javaClass.simpleName)
        }
        tunnel.onStateChanged(Tunnel.State.DOWN)
    }

    private suspend fun securelyRemoveManagedTunnel(tunnel: ObservableTunnel?) =
        withContext(NonCancellable + Dispatchers.Main.immediate) {
        if (tunnel == null) {
            managedNodeId = null
            managedServedNodeId = null
            managedLeaseId = null
            withContext(Dispatchers.IO) {
                runCatching { configStore.delete(XINGSUI_MANAGED_TUNNEL_NAME) }
            }
            return@withContext
        }
        stopManagedTunnelBackend(tunnel)
        tunnelMap.remove(tunnel)
        managedNodeId = null
        managedServedNodeId = null
        managedLeaseId = null
        if (lastUsedTunnel == tunnel) lastUsedTunnel = null
        withContext(Dispatchers.IO) {
            runCatching { configStore.delete(XINGSUI_MANAGED_TUNNEL_NAME) }
        }
        saveState()
    }

    private fun scheduleManagedLeaseExpiry(tunnel: ObservableTunnel, expiresAt: Instant) {
        managedLeaseExpiryJob?.cancel()
        val delayMillis = (expiresAt.toEpochMilli() - System.currentTimeMillis()).coerceAtLeast(0L)
        managedLeaseExpiryJob = applicationScope.launch {
            delay(delayMillis)
            withContext(Dispatchers.Main.immediate) {
                if (tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME] == tunnel) {
                    managedLeaseExpiryJob = null
                    securelyRemoveManagedTunnel(tunnel)
                }
            }
        }
    }

    suspend fun delete(tunnel: ObservableTunnel) = withContext(Dispatchers.Main.immediate) {
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
            securelyRemoveManagedTunnel(tunnel)
            return@withContext
        }
        val originalState = tunnel.state
        val wasLastUsed = tunnel == lastUsedTunnel
        // Make sure nothing touches the tunnel.
        if (wasLastUsed)
            lastUsedTunnel = null
        tunnelMap.remove(tunnel)
        try {
            if (originalState == Tunnel.State.UP) {
                stopUsageReporter(tunnel.name)
                withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.DOWN, null) }
            }
            try {
                withContext(Dispatchers.IO) { configStore.delete(tunnel.name) }
            } catch (e: Throwable) {
                if (originalState == Tunnel.State.UP)
                    withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.UP, tunnel.config) }
                throw e
            }
        } catch (e: Throwable) {
            // Failure, put the tunnel back.
            tunnelMap.add(tunnel)
            if (wasLastUsed)
                lastUsedTunnel = tunnel
            throw e
        }
    }

    @get:Bindable
    var lastUsedTunnel: ObservableTunnel? = null
        private set(value) {
            if (value == field) return
            field = value
            notifyPropertyChanged(BR.lastUsedTunnel)
            applicationScope.launch { UserKnobs.setLastUsedTunnel(value?.name) }
        }

    suspend fun getTunnelConfig(tunnel: ObservableTunnel): Config = withContext(Dispatchers.Main.immediate) {
        tunnel.onConfigChanged(withContext(Dispatchers.IO) { configStore.load(tunnel.name) })!!
    }

    fun onCreate() {
        applicationScope.launch {
            try {
                onTunnelsLoaded(withContext(Dispatchers.IO) { configStore.enumerate() }, withContext(Dispatchers.IO) { getBackend().runningTunnelNames })
                setupStatusCallbacks()
            } catch (e: Throwable) {
                Log.e(TAG, Log.getStackTraceString(e))
            }
        }
    }

    private fun setupStatusCallbacks() {
        applicationScope.launch {
            try {
                val backend = getBackend()
                val statusCallback = object : StatusCallback {
                    override fun onStatusChanged(connected: Boolean) {
                        applicationScope.launch(Dispatchers.Main) {
                            // Find the currently active tunnel
                            val activeTunnel = tunnelMap.firstOrNull { it.state == Tunnel.State.UP }
                            if (activeTunnel != null) {
                                val newStatus = if (connected) {
                                    ObservableTunnel.ConnectionStatus.CONNECTED
                                } else {
                                    ObservableTunnel.ConnectionStatus.CONNECTING
                                }
                                activeTunnel.onConnectionStatusChanged(newStatus)
                            }
                        }
                    }
                }
                
                backend.setStatusCallback(statusCallback)
            } catch (e: Throwable) {
                Log.e(TAG, "Failed to setup status callbacks", e)
            }
        }
    }

    private suspend fun onTunnelsLoaded(present: Iterable<String>, running: Collection<String>) {
        for (name in present.filterNot { it == XINGSUI_MANAGED_TUNNEL_NAME })
            addToList(name, null, if (running.contains(name)) Tunnel.State.UP else Tunnel.State.DOWN)
        if (running.contains(XINGSUI_MANAGED_TUNNEL_NAME)) {
            val staleManagedTunnel = addToList(
                XINGSUI_MANAGED_TUNNEL_NAME,
                null,
                Tunnel.State.UP,
            )
            securelyRemoveManagedTunnel(staleManagedTunnel)
        }
        val lastUsedName = UserKnobs.lastUsedTunnel.first()
        if (lastUsedName != null)
            lastUsedTunnel = tunnelMap[lastUsedName]
        haveLoaded = true
        restoreState(true)
        tunnels.complete(tunnelMap)
    }

    private fun refreshTunnelStates() {
        applicationScope.launch {
            try {
                val running = withContext(Dispatchers.IO) { getBackend().runningTunnelNames }
                for (tunnel in tunnelMap)
                    tunnel.onStateChanged(if (running.contains(tunnel.name)) Tunnel.State.UP else Tunnel.State.DOWN)
            } catch (e: Throwable) {
                Log.e(TAG, Log.getStackTraceString(e))
            }
        }
    }

    suspend fun restoreState(force: Boolean) {
        if (!haveLoaded || (!force && !UserKnobs.restoreOnBoot.first()))
            return
        val previouslyRunning = UserKnobs.runningTunnels.first()
        if (previouslyRunning.isEmpty()) return
        UserKnobs.setRunningTunnels(emptySet())
    }

    suspend fun saveState() {
        UserKnobs.setRunningTunnels(tunnelMap.filter { it.state == Tunnel.State.UP }.map { it.name }.toSet())
    }

    suspend fun setTunnelConfig(tunnel: ObservableTunnel, config: Config): Config = withContext(Dispatchers.Main.immediate) {
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME)
            throw XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
        tunnel.onConfigChanged(withContext(Dispatchers.IO) {
            getBackend().setState(tunnel, tunnel.state, config)
            configStore.save(tunnel.name, config)
        })!!
    }

    suspend fun setTunnelName(tunnel: ObservableTunnel, name: String): String = withContext(Dispatchers.Main.immediate) {
        if (Tunnel.isNameInvalid(name))
            throw IllegalArgumentException(context.getString(R.string.tunnel_error_invalid_name))
        if (tunnelMap.containsKey(name)) {
            throw IllegalArgumentException(context.getString(R.string.tunnel_error_already_exists, name))
        }
        val originalState = tunnel.state
        val wasLastUsed = tunnel == lastUsedTunnel
        // Make sure nothing touches the tunnel.
        if (wasLastUsed)
            lastUsedTunnel = null
        tunnelMap.remove(tunnel)
        var throwable: Throwable? = null
        var newName: String? = null
        try {
            if (originalState == Tunnel.State.UP)
                withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.DOWN, null) }
            withContext(Dispatchers.IO) { configStore.rename(tunnel.name, name) }
            newName = tunnel.onNameChanged(name)
            if (originalState == Tunnel.State.UP)
                withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.UP, tunnel.config) }
        } catch (e: Throwable) {
            throwable = e
            // On failure, we don't know what state the tunnel might be in. Fix that.
            getTunnelState(tunnel)
        }
        // Add the tunnel back to the manager, under whatever name it thinks it has.
        tunnelMap.add(tunnel)
        if (wasLastUsed)
            lastUsedTunnel = tunnel
        if (throwable != null)
            throw throwable
        newName!!
    }

    suspend fun setTunnelState(tunnel: ObservableTunnel, state: Tunnel.State): Tunnel.State = withContext(Dispatchers.Main.immediate) {
        if (willBringTunnelUp(tunnel, state)) {
            if (tunnel.name != XINGSUI_MANAGED_TUNNEL_NAME)
                throw XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
            return@withContext connectManagedTunnelInternal(nodeId = null, stopExistingFirst = false).state
        }
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
            securelyRemoveManagedTunnel(tunnel)
            return@withContext Tunnel.State.DOWN
        }
        var newState = tunnel.state
        var throwable: Throwable? = null
        try {
            newState = withContext(Dispatchers.IO) { getBackend().setState(tunnel, state, tunnel.getConfigAsync()) }
            if (newState == Tunnel.State.UP)
                lastUsedTunnel = tunnel
        } catch (e: Throwable) {
            throwable = e
        }
        tunnel.onStateChanged(newState)
        saveState()
        if (newState == Tunnel.State.UP && throwable == null)
            startUsageReporter(tunnel)
        else if (newState != Tunnel.State.UP)
            stopUsageReporter(tunnel.name)
        if (throwable != null)
            throw throwable
        newState
    }

    private fun willBringTunnelUp(tunnel: ObservableTunnel, state: Tunnel.State): Boolean {
        return state == Tunnel.State.UP || (state == Tunnel.State.TOGGLE && tunnel.state != Tunnel.State.UP)
    }

    class IntentReceiver : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent?) {
            applicationScope.launch {
                val manager = getTunnelManager()
                if (intent == null) return@launch
                val action = intent.action ?: return@launch
                if ("com.xingsui.vpn.action.REFRESH_TUNNEL_STATES" == action ||
                    "org.amnezia.awg.action.REFRESH_TUNNEL_STATES" == action
                ) {
                    manager.refreshTunnelStates()
                    return@launch
                }
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || !UserKnobs.allowRemoteControlIntents.first())
                    return@launch
                val state: Tunnel.State
                state = when (action) {
                    "com.xingsui.vpn.action.SET_TUNNEL_UP" -> Tunnel.State.UP
                    "com.xingsui.vpn.action.SET_TUNNEL_DOWN" -> Tunnel.State.DOWN
                    "org.amnezia.awg.action.SET_TUNNEL_UP" -> Tunnel.State.UP
                    "org.amnezia.awg.action.SET_TUNNEL_DOWN" -> Tunnel.State.DOWN
                    else -> return@launch
                }
                val tunnelName = intent.getStringExtra("tunnel") ?: return@launch
                val tunnels = manager.getTunnels()
                val tunnel = tunnels[tunnelName] ?: return@launch
                try {
                    manager.setTunnelState(tunnel, state)
                } catch (e: Throwable) {
                    Toast.makeText(context, ErrorMessages[e], Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    suspend fun getTunnelState(tunnel: ObservableTunnel): Tunnel.State = withContext(Dispatchers.Main.immediate) {
        tunnel.onStateChanged(withContext(Dispatchers.IO) { getBackend().getState(tunnel) })
    }

    suspend fun getTunnelStatistics(tunnel: ObservableTunnel): Statistics = withContext(Dispatchers.Main.immediate) {
        tunnel.onStatisticsChanged(withContext(Dispatchers.IO) { getBackend().getStatistics(tunnel) })!!
    }

    private fun startUsageReporter(tunnel: ObservableTunnel) {
        stopUsageReporter(tunnel.name)
        usageReporterJobs[tunnel.name] = applicationScope.launch {
            var lastRx = 0L
            var lastTx = 0L
            var consecutiveReportFailures = 0
            val connectedAtMs = System.currentTimeMillis()
            while (true) {
                delay(USAGE_REPORT_INTERVAL_MS)
                try {
                    val statistics = withContext(Dispatchers.IO) { getBackend().getStatistics(tunnel) }

                    // Dead-link watchdog: the app is excluded from the tunnel, so API calls
                    // keep succeeding even when the data path is dead (e.g. carrier kills the
                    // UDP flow). A healthy AWG link re-handshakes at least every ~2-3 min with
                    // keepalive 25s; a stale handshake means the tunnel passes no data.
                    if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME && tunnel.state == Tunnel.State.UP) {
                        val latestHandshakeAt = statistics.peers().maxOfOrNull { peer ->
                            statistics.peer(peer)?.latestHandshakeEpochMillis() ?: 0L
                        } ?: 0L
                        val nowMs = System.currentTimeMillis()
                        val linkDead = if (latestHandshakeAt > 0L)
                            nowMs - latestHandshakeAt > DEAD_LINK_STALE_HANDSHAKE_MS
                        else
                            nowMs - connectedAtMs > DEAD_LINK_NO_HANDSHAKE_MS
                        if (linkDead) {
                            handleDeadManagedLink()
                            return@launch
                        }
                    }

                    val rx = statistics.totalRx()
                    val tx = statistics.totalTx()
                    val rxDelta = (rx - lastRx).coerceAtLeast(0L)
                    val txDelta = (tx - lastTx).coerceAtLeast(0L)
                    lastRx = rx
                    lastTx = tx

                    val session = XingsuiSessionStore(context).load()
                        ?: throw XingsuiUsageSessionGoneException()
                    val leaseId = managedLeaseId
                        ?: throw XingsuiUsageSessionGoneException()
                    val entitlement = XingsuiApiClient(accessToken = session.accessToken)
                        .reportUsage(leaseId, tunnel.name, rxDelta, txDelta)
                    val now = Instant.now()
                    val renewedExpiry = entitlement.leaseExpiresAt
                    if (!entitlement.allowed ||
                        renewedExpiry?.isAfter(now) != true ||
                        renewedExpiry.isAfter(now.plusSeconds(MAX_RENEWED_LEASE_SECONDS))
                    ) {
                        if (!entitlement.allowed && entitlement.reason.isNotBlank())
                            managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.EntitlementDenied(entitlement.reason))
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    consecutiveReportFailures = 0
                    withContext(Dispatchers.Main.immediate) {
                        if (tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME] == tunnel) {
                            scheduleManagedLeaseExpiry(tunnel, renewedExpiry)
                        }
                    }
                } catch (e: Throwable) {
                    if (e is CancellationException) throw e
                    // The session/lease being gone is not transient — stop immediately.
                    // Network hiccups on the report call get a few retry cycles before we
                    // give up: the lease is renewed for minutes, one lost report is harmless.
                    if (e is XingsuiUsageSessionGoneException) {
                        Log.e(TAG, "Xingsui session/lease gone while reporting usage", e)
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    consecutiveReportFailures++
                    Log.e(TAG, "Failed to report Xingsui traffic usage ($consecutiveReportFailures/$MAX_REPORT_FAILURES)", e)
                    if (consecutiveReportFailures >= MAX_REPORT_FAILURES) {
                        managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.ReportFailureDisconnected)
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                }
            }
        }
    }

    private class XingsuiUsageSessionGoneException : IllegalStateException("xingsui_session_or_lease_gone")

    /**
     * The managed tunnel's data path is dead while the control plane still works.
     * For smart-connect sessions, try one automatic reconnect that asks the backend to
     * exclude the failed node; for manually-picked nodes (or if the switch fails), tear
     * down and tell the UI why.
     */
    private suspend fun handleDeadManagedLink() {
        usageReporterJobs.remove(XINGSUI_MANAGED_TUNNEL_NAME)
        val servedNode = managedServedNodeId
        val manualNode = managedNodeId
        XingsuiCrashReporter.recordEvent("managed-dead-link", servedNode ?: "unknown")
        if (manualNode == null && autoSwitchAttempts < MAX_AUTO_SWITCH_ATTEMPTS) {
            autoSwitchAttempts++
            managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.DeadLinkSwitching)
            try {
                connectManagedTunnelInternal(
                    nodeId = null,
                    stopExistingFirst = true,
                    excludeNodeId = servedNode,
                )
                managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.DeadLinkSwitched)
                return
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                XingsuiCrashReporter.recordEvent("managed-dead-link-switch-failed", e.javaClass.simpleName)
            }
        }
        withContext(Dispatchers.Main.immediate) {
            securelyRemoveManagedTunnel(tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME])
        }
        managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.DeadLinkDisconnected)
    }

    private fun stopUsageReporter(tunnelName: String) {
        usageReporterJobs.remove(tunnelName)?.cancel()
    }

    private suspend fun stopTunnelAfterEntitlementFailure(tunnel: ObservableTunnel) = withContext(Dispatchers.Main.immediate) {
        usageReporterJobs.remove(tunnel.name)
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
            securelyRemoveManagedTunnel(tunnel)
            return@withContext
        }
        if (tunnel.state != Tunnel.State.UP)
            return@withContext
        try {
            val newState = withContext(Dispatchers.IO) { getBackend().setState(tunnel, Tunnel.State.DOWN, null) }
            tunnel.onStateChanged(newState)
            saveState()
        } catch (e: Throwable) {
            Log.e(TAG, "Failed to stop tunnel after Xingsui entitlement failure", e)
        }
    }

    companion object {
        private const val TAG = "AmneziaWG/TunnelManager"
        private const val XINGSUI_MANAGED_TUNNEL_NAME = "xingsui"
        private const val USAGE_REPORT_INTERVAL_MS = 10_000L
        private const val MAX_RENEWED_LEASE_SECONDS = 15 * 60L
        private const val MAX_REPORT_FAILURES = 3
        private const val MAX_AUTO_SWITCH_ATTEMPTS = 1
        // Keepalive is 25s; a live AWG link re-handshakes at least every ~2-3 min.
        private const val DEAD_LINK_STALE_HANDSHAKE_MS = 180_000L
        private const val DEAD_LINK_NO_HANDSHAKE_MS = 60_000L
    }
}
