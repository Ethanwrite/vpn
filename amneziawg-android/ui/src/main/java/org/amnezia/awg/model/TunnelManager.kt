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
import org.amnezia.awg.xingsui.api.XingsuiHttpException
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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
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
    private val managedConnectionMutex = Mutex()

    /** UI-facing notifications for managed-tunnel teardowns that the user didn't initiate. */
    sealed class ManagedTunnelEvent {
        object DeadLinkSwitching : ManagedTunnelEvent()
        object DeadLinkSwitched : ManagedTunnelEvent()
        object DeadLinkDisconnected : ManagedTunnelEvent()
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
        return connectManagedTunnelInternal(nodeId = nodeId)
    }

    suspend fun reconnectManagedTunnel(tunnel: ObservableTunnel): ObservableTunnel {
        require(tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME)
        autoSwitchAttempts = 0
        return connectManagedTunnelInternal(nodeId = managedNodeId)
    }

    private suspend fun connectManagedTunnelInternal(
        nodeId: String?,
        excludeNodeId: String? = null,
        requireRestoreIntent: Boolean = false,
    ): ObservableTunnel = managedConnectionMutex.withLock {
        withContext(Dispatchers.Main.immediate) {
            var target = tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME]
            val targetWasUp = target?.state == Tunnel.State.UP
            try {
                if (
                    requireRestoreIntent &&
                    XINGSUI_MANAGED_TUNNEL_NAME !in UserKnobs.runningTunnels.first()
                ) {
                    throw ManagedRestoreCancelledException()
                }
                val backend = getBackend()
                if (backend is GoBackend && GoBackend.VpnService.prepare(context) != null) {
                    throw XingsuiConnectionSyncException(context.getString(R.string.xingsui_account_sync_failed))
                }

                // Fetch and validate first. GoBackend switches configs transactionally and
                // restores the old config if activation fails, so a transient control-plane
                // or network error must never tear down a working tunnel first.
                val fresh = XingsuiVipGate.requireFreshManagedConfig(context, nodeId, excludeNodeId)
                val managedTunnel = target ?: addToList(
                    XINGSUI_MANAGED_TUNNEL_NAME,
                    withContext(Dispatchers.IO) {
                        configStore.create(XINGSUI_MANAGED_TUNNEL_NAME, fresh.config)
                    },
                    Tunnel.State.DOWN,
                ).also { target = it }

                withContext(NonCancellable) {
                    val newState = withContext(Dispatchers.IO) {
                        backend.setState(managedTunnel, Tunnel.State.UP, fresh.config)
                    }
                    managedTunnel.onStateChanged(newState)
                    check(newState == Tunnel.State.UP) { "managed_tunnel_not_started" }

                    // Commit the in-memory config and lease identity in the same
                    // non-cancellable section as backend activation. Otherwise a network
                    // callback cancellation can leave a new data plane reporting an old ID.
                    managedTunnel.onConfigChanged(fresh.config)
                    managedNodeId = nodeId
                    managedServedNodeId = fresh.response.id
                    managedLeaseId = fresh.response.leaseId
                    lastUsedTunnel = managedTunnel
                    scheduleManagedLeaseExpiry(managedTunnel, fresh.response.expiresAt)
                    startUsageReporter(managedTunnel)
                    runCatching { saveState() }
                        .onFailure { XingsuiCrashReporter.recordException("managed-state-save", it) }

                    // Persist only after the backend accepted the config. A persistence
                    // error is non-fatal because managed configs are refreshed before reuse.
                    runCatching {
                        withContext(Dispatchers.IO) {
                            configStore.save(XINGSUI_MANAGED_TUNNEL_NAME, fresh.config)
                        }
                    }.onFailure {
                        XingsuiCrashReporter.recordException("managed-config-save", it)
                    }
                }
                managedTunnel
            } catch (error: Throwable) {
                // Preserve an already-running tunnel on refresh/reconnect failures. Explicit
                // entitlement denial is authoritative and still tears it down immediately.
                if (!targetWasUp || error is XingsuiEntitlementException) {
                    withContext(NonCancellable) {
                        securelyRemoveManagedTunnelLocked(target)
                        if (
                            requireRestoreIntent &&
                            error !is XingsuiEntitlementException &&
                            error !is ManagedRestoreCancelledException
                        ) {
                            UserKnobs.setRunningTunnels(setOf(XINGSUI_MANAGED_TUNNEL_NAME))
                        }
                    }
                }
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
        managedConnectionMutex.withLock { securelyRemoveManagedTunnelLocked(tunnel) }

    /** Caller must hold [managedConnectionMutex]. */
    private suspend fun securelyRemoveManagedTunnelLocked(tunnel: ObservableTunnel?) =
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
                    // Doze can suspend both this timer and the reporter. Do not convert that
                    // expected suspension into a user-visible disconnect; the reporter will
                    // transparently reacquire an expired lease as soon as the app wakes.
                    XingsuiCrashReporter.recordEvent("managed-lease-expired", "awaiting-transparent-recovery")
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
        val previouslyRunning = UserKnobs.runningTunnels.first()
        val restoreManaged = XINGSUI_MANAGED_TUNNEL_NAME in previouslyRunning
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
        tunnels.complete(tunnelMap)
        if (restoreManaged) {
            // Removing a stale process-owned backend above saves the observed DOWN state;
            // restore the user's prior intent before requesting a fresh short-lived lease.
            UserKnobs.setRunningTunnels(previouslyRunning)
        }
        restoreState(true)
    }

    private fun refreshTunnelStates() {
        applicationScope.launch {
            try {
                val backend = getBackend()
                val running = withContext(Dispatchers.IO) { backend.runningTunnelNames }
                for (tunnel in tunnelMap.filterNot { it.name == XINGSUI_MANAGED_TUNNEL_NAME }) {
                    tunnel.onStateChanged(if (running.contains(tunnel.name)) Tunnel.State.UP else Tunnel.State.DOWN)
                }
                managedConnectionMutex.withLock {
                    val managedTunnel = tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME]
                    if (managedTunnel != null) {
                        val managedState = withContext(Dispatchers.IO) { backend.getState(managedTunnel) }
                        // Read and apply under the same lock: never carry a stale DOWN
                        // observation across a completed reconnect that replaced the state.
                        managedTunnel.onStateChanged(managedState)
                    }
                }
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
        if (XINGSUI_MANAGED_TUNNEL_NAME !in previouslyRunning) {
            UserKnobs.setRunningTunnels(emptySet())
            return
        }
        if (tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME]?.state == Tunnel.State.UP) return
        if (XingsuiSessionStore(context).load() == null) {
            UserKnobs.setRunningTunnels(emptySet())
            return
        }
        try {
            connectManagedTunnelInternal(nodeId = null, requireRestoreIntent = true)
        } catch (error: CancellationException) {
            throw error
        } catch (error: XingsuiEntitlementException) {
            UserKnobs.setRunningTunnels(emptySet())
            managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.EntitlementDenied(error.reason))
        } catch (error: Throwable) {
            // Preserve intent. A later validated-network callback retries recovery.
            UserKnobs.setRunningTunnels(setOf(XINGSUI_MANAGED_TUNNEL_NAME))
            XingsuiCrashReporter.recordException("managed-restore", error)
        }
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
            return@withContext connectManagedTunnelInternal(nodeId = null).state
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

    suspend fun getTunnelState(tunnel: ObservableTunnel): Tunnel.State {
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
            return managedConnectionMutex.withLock {
                withContext(Dispatchers.Main.immediate) {
                    tunnel.onStateChanged(withContext(Dispatchers.IO) { getBackend().getState(tunnel) })
                }
            }
        }
        return withContext(Dispatchers.Main.immediate) {
            tunnel.onStateChanged(withContext(Dispatchers.IO) { getBackend().getState(tunnel) })
        }
    }

    suspend fun getTunnelStatistics(tunnel: ObservableTunnel): Statistics {
        if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
            return managedConnectionMutex.withLock {
                withContext(Dispatchers.Main.immediate) {
                    tunnel.onStatisticsChanged(withContext(Dispatchers.IO) { getBackend().getStatistics(tunnel) })!!
                }
            }
        }
        return withContext(Dispatchers.Main.immediate) {
            tunnel.onStatisticsChanged(withContext(Dispatchers.IO) { getBackend().getStatistics(tunnel) })!!
        }
    }

    private fun startUsageReporter(tunnel: ObservableTunnel) {
        stopUsageReporter(tunnel.name)
        usageReporterJobs[tunnel.name] = applicationScope.launch {
            var lastRx = 0L
            var lastTx = 0L
            var validatedNoHandshakeSamples = 0
            while (true) {
                delay(USAGE_REPORT_INTERVAL_MS)
                try {
                    val statistics = withContext(Dispatchers.IO) { getBackend().getStatistics(tunnel) }

                    // An empty statistics snapshot is UNKNOWN (the native backend can return
                    // it transiently), not proof of a dead link. Only rotate when a real peer
                    // exists and the initial handshake never arrives. A stale historical
                    // handshake alone is not safe evidence: idle healthy AWG peers can exceed
                    // 180 seconds without a new handshake.
                    if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME && tunnel.state == Tunnel.State.UP) {
                        val handshakes = statistics.peers().map { peer ->
                            statistics.peer(peer)?.latestHandshakeEpochMillis() ?: 0L
                        }
                        val physicalNetworkValidated = org.amnezia.awg.Application.getNetworkState().isConnected()
                        validatedNoHandshakeSamples = if (
                            physicalNetworkValidated && handshakes.isNotEmpty() && handshakes.all { it <= 0L }
                        ) {
                            validatedNoHandshakeSamples + 1
                        } else {
                            0
                        }
                        val initialHandshakeMissing =
                            validatedNoHandshakeSamples >= DEAD_LINK_NO_HANDSHAKE_SAMPLES
                        if (initialHandshakeMissing) {
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
                    withContext(Dispatchers.Main.immediate) {
                        if (tunnelMap[XINGSUI_MANAGED_TUNNEL_NAME] == tunnel) {
                            scheduleManagedLeaseExpiry(tunnel, renewedExpiry)
                        }
                    }
                } catch (e: Throwable) {
                    if (e is CancellationException) throw e
                    if (e is XingsuiUsageSessionGoneException) {
                        Log.e(TAG, "Xingsui session/lease gone while reporting usage", e)
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    val httpError = e.findXingsuiHttpException()
                    val detail = httpError?.detail()
                    if (httpError?.isUnauthorized == true) {
                        XingsuiSessionStore(context).clear()
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    if (httpError?.statusCode == 403 && detail == "Account disabled") {
                        XingsuiSessionStore(context).clear()
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    if (detail in ENTITLEMENT_DENIAL_REASONS) {
                        managedTunnelEventsFlow.tryEmit(ManagedTunnelEvent.EntitlementDenied(detail.orEmpty()))
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    if (detail in RECOVERABLE_LEASE_ERRORS) {
                        try {
                            connectManagedTunnelInternal(
                                nodeId = managedNodeId,
                                excludeNodeId = if (managedNodeId == null && detail == "vpn_node_unavailable") {
                                    managedServedNodeId
                                } else {
                                    null
                                },
                            )
                            return@launch
                        } catch (recoveryError: CancellationException) {
                            throw recoveryError
                        } catch (recoveryError: Throwable) {
                            Log.w(TAG, "Managed lease recovery will be retried", recoveryError)
                        }
                    }
                    if (httpError?.statusCode == 403) {
                        // Any remaining 403 is an explicit server-side denial, not a
                        // transport blip. Keeping a UI-UP tunnel until peer expiry would be
                        // a silent black hole.
                        stopTunnelAfterEntitlementFailure(tunnel)
                        return@launch
                    }
                    // I/O, timeout and 5xx failures are not entitlement decisions. Keep the
                    // data plane up and retry; an expired lease will take the recovery path.
                    Log.w(TAG, "Failed to report Xingsui traffic usage; keeping tunnel up", e)
                }
            }
        }
    }

    private fun Throwable.findXingsuiHttpException(): XingsuiHttpException? {
        var current: Throwable? = this
        val seen = mutableSetOf<Throwable>()
        while (current != null && seen.add(current)) {
            if (current is XingsuiHttpException) return current
            current = current.cause
        }
        return null
    }

    private fun XingsuiHttpException.detail(): String = runCatching {
        JSONObject(responseBody).optString("detail").trim()
    }.getOrDefault("")

    private class ManagedRestoreCancelledException : CancellationException("managed_restore_no_longer_requested")

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
        private const val USAGE_REPORT_INTERVAL_MS = 30_000L
        private const val MAX_RENEWED_LEASE_SECONDS = 60 * 60L + 90L
        private const val MAX_AUTO_SWITCH_ATTEMPTS = 1
        private const val DEAD_LINK_NO_HANDSHAKE_SAMPLES = 2
        private val RECOVERABLE_LEASE_ERRORS = setOf(
            "invalid_vpn_lease",
            "vpn_lease_expired",
            "vpn_lease_cannot_be_renewed",
            "vpn_node_unavailable",
            "vpn_lease_renewal_failed",
        )
        private val ENTITLEMENT_DENIAL_REASONS =
            setOf("free_traffic_exhausted", "vip_expired", "vip_required")
    }
}
