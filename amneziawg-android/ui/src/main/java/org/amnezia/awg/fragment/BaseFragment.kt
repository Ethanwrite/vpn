/*
 * Copyright © 2017-2023 WireGuard LLC. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */
package org.amnezia.awg.fragment

import android.content.Context
import android.app.Activity
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.databinding.DataBindingUtil
import androidx.databinding.ViewDataBinding
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import org.amnezia.awg.Application
import org.amnezia.awg.R
import org.amnezia.awg.activity.BaseActivity
import org.amnezia.awg.activity.BaseActivity.OnSelectedTunnelChangedListener
import org.amnezia.awg.backend.GoBackend
import org.amnezia.awg.backend.Tunnel
import org.amnezia.awg.databinding.TunnelDetailFragmentBinding
import org.amnezia.awg.databinding.TunnelListItemBinding
import org.amnezia.awg.model.ObservableTunnel
import kotlinx.coroutines.launch

/**
 * Base class for fragments that need to know the currently-selected tunnel. Only does anything when
 * attached to a `BaseActivity`.
 */
abstract class BaseFragment : Fragment(), OnSelectedTunnelChangedListener {
    private var pendingTunnel: ObservableTunnel? = null
    private var pendingTunnelUp: Boolean? = null
    private val permissionActivityResultLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val tunnel = pendingTunnel
        val checked = pendingTunnelUp
        if (result.resultCode == Activity.RESULT_OK && tunnel != null && checked != null) {
            setTunnelStateWithPermissionsResult(tunnel, checked)
        } else if (checked == true) {
            if (tunnel?.name == XINGSUI_MANAGED_TUNNEL_NAME) {
                Application.getCoroutineScope().launch { runCatching { tunnel.deleteAsync() } }
            }
            showSyncFailure()
        }
        pendingTunnel = null
        pendingTunnelUp = null
    }

    protected var selectedTunnel: ObservableTunnel?
        get() = (activity as? BaseActivity)?.selectedTunnel
        protected set(tunnel) {
            (activity as? BaseActivity)?.selectedTunnel = tunnel
        }

    override fun onAttach(context: Context) {
        super.onAttach(context)
        (activity as? BaseActivity)?.addOnSelectedTunnelChangedListener(this)
    }

    override fun onDetach() {
        (activity as? BaseActivity)?.removeOnSelectedTunnelChangedListener(this)
        super.onDetach()
    }

    fun setTunnelState(view: View, checked: Boolean) {
        val tunnel = when (val binding = DataBindingUtil.findBinding<ViewDataBinding>(view)) {
            is TunnelDetailFragmentBinding -> binding.tunnel
            is TunnelListItemBinding -> binding.item
            else -> return
        } ?: return
        val activity = activity ?: return
        activity.lifecycleScope.launch {
            if (checked && Application.getBackend() is GoBackend) {
                try {
                    val intent = GoBackend.VpnService.prepare(activity)
                    if (intent != null) {
                        pendingTunnel = tunnel
                        pendingTunnelUp = checked
                        permissionActivityResultLauncher.launch(intent)
                        return@launch
                    }
                } catch (e: Throwable) {
                    if (tunnel.name == XINGSUI_MANAGED_TUNNEL_NAME) {
                        Application.getCoroutineScope().launch { runCatching { tunnel.deleteAsync() } }
                    }
                    val message = activity.getString(R.string.xingsui_account_sync_failed)
                    Snackbar.make(view, message, Snackbar.LENGTH_LONG)
                        .setAnchorView(view.findViewById(R.id.create_fab))
                        .show()
                    Log.e(TAG, "Managed VPN permission preparation failed", e)
                    return@launch
                }
            }
            setTunnelStateWithPermissionsResult(tunnel, checked)
        }
    }

    private fun setTunnelStateWithPermissionsResult(tunnel: ObservableTunnel, checked: Boolean) {
        val activity = activity ?: return
        activity.lifecycleScope.launch {
            try {
                tunnel.setStateAsync(Tunnel.State.of(checked))
            } catch (e: Throwable) {
                val message = activity.getString(R.string.xingsui_account_sync_failed)
                val view = view
                if (view != null)
                    Snackbar.make(view, message, Snackbar.LENGTH_LONG)
                        .setAnchorView(view.findViewById(R.id.create_fab))
                        .show()
                else
                    Toast.makeText(activity, message, Toast.LENGTH_LONG).show()
                Log.e(TAG, "Managed tunnel state change failed", e)
            }
        }
    }

    private fun showSyncFailure() {
        val activity = activity ?: return
        val currentView = view
        if (currentView != null) {
            Snackbar.make(currentView, R.string.xingsui_account_sync_failed, Snackbar.LENGTH_LONG)
                .setAnchorView(currentView.findViewById(R.id.create_fab))
                .show()
        } else {
            Toast.makeText(activity, R.string.xingsui_account_sync_failed, Toast.LENGTH_LONG).show()
        }
    }

    companion object {
        private const val TAG = "AmneziaWG/BaseFragment"
        private const val XINGSUI_MANAGED_TUNNEL_NAME = "xingsui"
    }
}
