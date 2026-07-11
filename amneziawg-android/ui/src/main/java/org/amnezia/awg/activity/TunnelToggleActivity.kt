/*
 * Copyright © 2017-2023 WireGuard LLC. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */
package org.amnezia.awg.activity

import android.content.ComponentName
import android.app.Activity
import android.os.Bundle
import android.service.quicksettings.TileService
import android.util.Log
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import org.amnezia.awg.Application
import org.amnezia.awg.QuickTileService
import org.amnezia.awg.R
import org.amnezia.awg.backend.GoBackend
import org.amnezia.awg.backend.Tunnel
import kotlinx.coroutines.launch

class TunnelToggleActivity : AppCompatActivity() {
    private val permissionActivityResultLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                toggleTunnelWithPermissionsResult()
            } else {
                discardManagedTunnelAndFinish()
            }
        }

    private fun toggleTunnelWithPermissionsResult() {
        val tunnel = Application.getTunnelManager().lastUsedTunnel
            ?.takeIf { it.name == XINGSUI_MANAGED_TUNNEL_NAME }
            ?: return
        lifecycleScope.launch {
            try {
                tunnel.setStateAsync(Tunnel.State.TOGGLE)
            } catch (e: Throwable) {
                TileService.requestListeningState(this@TunnelToggleActivity, ComponentName(this@TunnelToggleActivity, QuickTileService::class.java))
                Log.e(TAG, "Managed tunnel toggle failed", e)
                Toast.makeText(
                    this@TunnelToggleActivity,
                    R.string.xingsui_account_sync_failed,
                    Toast.LENGTH_LONG,
                ).show()
                finishAffinity()
                return@launch
            }
            TileService.requestListeningState(this@TunnelToggleActivity, ComponentName(this@TunnelToggleActivity, QuickTileService::class.java))
            finishAffinity()
        }
    }

    private fun discardManagedTunnelAndFinish() {
        lifecycleScope.launch {
            Application.getTunnelManager().lastUsedTunnel
                ?.takeIf { it.name == XINGSUI_MANAGED_TUNNEL_NAME }
                ?.let { runCatching { it.deleteAsync() } }
            Toast.makeText(
                this@TunnelToggleActivity,
                R.string.xingsui_account_sync_failed,
                Toast.LENGTH_LONG,
            ).show()
            finishAffinity()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            val tunnel = Application.getTunnelManager().lastUsedTunnel
                ?.takeIf { it.name == XINGSUI_MANAGED_TUNNEL_NAME }
                ?: run {
                    finishAffinity()
                    return@launch
                }
            try {
                if (tunnel.state != Tunnel.State.UP && Application.getBackend() is GoBackend) {
                    val intent = GoBackend.VpnService.prepare(this@TunnelToggleActivity)
                    if (intent != null) {
                        permissionActivityResultLauncher.launch(intent)
                        return@launch
                    }
                }
            } catch (error: Throwable) {
                Log.e(TAG, "Managed VPN permission preparation failed", error)
                discardManagedTunnelAndFinish()
                return@launch
            }
            toggleTunnelWithPermissionsResult()
        }
    }

    companion object {
        private const val TAG = "AmneziaWG/TunnelToggleActivity"
        private const val XINGSUI_MANAGED_TUNNEL_NAME = "xingsui"
    }
}
