/*
 * Copyright © 2025 AmneziaWG. All Rights conneserved.
 * SPDX-License-Identifier: Apache-2.0
 */

package org.amnezia.awg.util

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.ConnectivityManager.NetworkCallback
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED
import android.net.NetworkCapabilities.TRANSPORT_CELLULAR
import android.net.NetworkCapabilities.TRANSPORT_WIFI
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.core.content.getSystemService
import kotlinx.coroutines.delay

private const val TAG = "AmneziaWG/NetworkState"
private const val BIND_NETWORK_RETRY_ATTEMPTS = 5

enum class NetworkType {
    NONE, WIFI, CELLULAR, OTHER
}

class NetworkState(
    private val context: Context,
    private val onNetworkChange: (NetworkType, NetworkType) -> Unit
) {
    private var currentNetwork: Network? = null
    private var currentNetworkType: NetworkType = NetworkType.NONE
    private var validated: Boolean = false
    private var isListenerBound = false
    private val candidates = linkedMapOf<Network, Candidate>()

    private data class Candidate(val type: NetworkType, val validated: Boolean)

    private val handler: Handler by lazy {
        Handler(Looper.getMainLooper())
    }

    private val connectivityManager: ConnectivityManager by lazy {
        context.getSystemService<ConnectivityManager>()!!
    }

    private val networkCallback: NetworkCallback by lazy {
        object : NetworkCallback() {
            override fun onAvailable(network: Network) {
                Log.d(TAG, "onAvailable: $network")
            }

            override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
                val newNetworkType = getNetworkType(networkCapabilities)
                val isValidated = networkCapabilities.hasCapability(NET_CAPABILITY_VALIDATED)
                Log.d(TAG, "onCapabilitiesChanged: network=$network, type=$newNetworkType, validated=$isValidated")
                handler.post {
                    if (!isListenerBound) return@post
                    candidates[network] = Candidate(newNetworkType, isValidated)
                    updateSelectedNetwork()
                }
            }

            private fun getNetworkType(capabilities: NetworkCapabilities): NetworkType {
                return when {
                    capabilities.hasTransport(TRANSPORT_WIFI) -> NetworkType.WIFI
                    capabilities.hasTransport(TRANSPORT_CELLULAR) -> NetworkType.CELLULAR
                    else -> NetworkType.OTHER
                }
            }

            override fun onLost(network: Network) {
                Log.d(TAG, "onLost: $network, currentNetwork: $currentNetwork")
                handler.post {
                    if (!isListenerBound) return@post
                    candidates.remove(network)
                    updateSelectedNetwork()
                }
            }
        }
    }

    /**
     * API 26-30 can report every matching Wi-Fi and cellular network. Keep one stable,
     * validated physical network so callback order cannot flap the VPN between candidates.
     */
    private fun updateSelectedNetwork() {
        val oldNetwork = currentNetwork
        val oldType = currentNetworkType
        val oldValidated = validated
        val best = candidates
            .filterValues { it.validated }
            .maxByOrNull { (_, candidate) -> networkPriority(candidate.type) }
        val currentCandidate = oldNetwork?.let(candidates::get)?.takeIf { it.validated }
        val selected = if (
            currentCandidate != null && best != null &&
            networkPriority(currentCandidate.type) >= networkPriority(best.value.type)
        ) {
            oldNetwork to currentCandidate
        } else {
            best?.let { it.key to it.value }
        }

        currentNetwork = selected?.first
        currentNetworkType = selected?.second?.type ?: NetworkType.NONE
        validated = selected?.second?.validated == true

        val changed = oldNetwork != currentNetwork
        val recovered = !oldValidated && validated && oldNetwork == currentNetwork
        if (changed || recovered) {
            val selectedType = currentNetworkType
            Log.d(TAG, "Selected network changed: $oldType -> $selectedType, validated=$validated")
            handler.post { onNetworkChange(oldType, selectedType) }
        }
    }

    private fun networkPriority(type: NetworkType): Int = when (type) {
        NetworkType.WIFI -> 3
        NetworkType.OTHER -> 2
        NetworkType.CELLULAR -> 1
        NetworkType.NONE -> 0
    }

    suspend fun bindNetworkListener() {
        if (isListenerBound) {
            Log.d(TAG, "Network listener already bound")
            return
        }

        // Check if we have the required permission
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_NETWORK_STATE) != PackageManager.PERMISSION_GRANTED) {
            Log.e(TAG, "ACCESS_NETWORK_STATE permission not granted, cannot bind network listener")
            return
        }

        Log.i(TAG, "Binding network listener (SDK ${Build.VERSION.SDK_INT})")

        var attemptCount = 0
        while (true) {
            try {
                // Set before registration so an immediately-posted initial callback is not
                // discarded on the main handler. Reset on every failed registration attempt.
                isListenerBound = true
                when {
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.O -> {
                        connectivityManager.registerDefaultNetworkCallback(networkCallback, handler)
                    }
                    else -> {
                        connectivityManager.registerDefaultNetworkCallback(networkCallback)
                    }
                }
                Log.i(TAG, "Network listener bound successfully")
                break
            } catch (e: SecurityException) {
                isListenerBound = false
                Log.e(TAG, "Failed to bind network listener: $e")
                // Android 11 bug: https://issuetracker.google.com/issues/175055271
                if (e.message?.startsWith("Package android does not belong to") == true) {
                    if (++attemptCount >= BIND_NETWORK_RETRY_ATTEMPTS) {
                        throw e
                    }
                    delay(1000)
                    continue
                } else {
                    throw e
                }
            } catch (e: Exception) {
                isListenerBound = false
                Log.e(TAG, "Failed to bind network listener", e)
                throw e
            }
        }
    }

    fun unbindNetworkListener() {
        if (!isListenerBound) {
            Log.d(TAG, "Network listener not bound, nothing to unbind")
            return
        }
        Log.d(TAG, "Unbind network listener")

        try {
            connectivityManager.unregisterNetworkCallback(networkCallback)
            Log.d(TAG, "Network listener unbound successfully")
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException while unbinding network listener", e)
        } catch (e: IllegalArgumentException) {
            // Callback was not registered, ignore
            Log.w(TAG, "Callback was not registered", e)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to unbind network listener", e)
        }

        isListenerBound = false
        currentNetwork = null
        currentNetworkType = NetworkType.NONE
        validated = false
        candidates.clear()
    }

    fun getCurrentNetworkType(): NetworkType = currentNetworkType

    fun isConnected(): Boolean = validated && currentNetworkType != NetworkType.NONE
}
