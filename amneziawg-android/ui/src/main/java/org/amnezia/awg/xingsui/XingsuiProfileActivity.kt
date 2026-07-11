package org.amnezia.awg.xingsui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.launch
import org.amnezia.awg.BuildConfig
import org.amnezia.awg.R
import org.amnezia.awg.databinding.XingsuiProfileActivityBinding
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException
import org.amnezia.awg.xingsui.model.UserAccount
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class XingsuiProfileActivity : AppCompatActivity() {
    private lateinit var binding: XingsuiProfileActivityBinding
    private lateinit var sessionStore: XingsuiSessionStore
    private var apiClient: XingsuiApiClient? = null
    private var account: UserAccount? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = XingsuiProfileActivityBinding.inflate(layoutInflater)
        sessionStore = XingsuiSessionStore(this)
        setContentView(binding.root)
        supportActionBar?.hide()

        val session = sessionStore.load()
        if (session == null) {
            openAuth()
            return
        }

        apiClient = XingsuiApiClient(accessToken = session.accessToken)
        binding.profileEmail.text = session.email
        binding.profileAvatar.text = session.email.firstOrNull()?.uppercaseChar()?.toString() ?: "星"
        binding.profileInviteDetail.text = session.inviteCode
        binding.profileVersionDetail.text = getString(R.string.xingsui_profile_update_hint, BuildConfig.VERSION_NAME)

        binding.profileBack.setOnClickListener { finish() }
        binding.profileWebsite.setOnClickListener { openUri(WEBSITE_URL) }
        binding.profileInvite.setOnClickListener { copyInviteCode() }
        binding.profileUpdate.setOnClickListener { lifecycleScope.launch { checkUpdate() } }
        binding.profileLogout.setOnClickListener { logout() }
    }

    override fun onResume() {
        super.onResume()
        if (sessionStore.load() != null) {
            lifecycleScope.launch { refreshAccount() }
        }
    }

    private suspend fun refreshAccount() {
        val client = apiClient ?: return
        runCatching { client.getMe() }
            .onSuccess {
                account = it
                renderAccount(it)
            }
            .onFailure { error ->
                if (error.isUnauthorized()) {
                    sessionStore.clear()
                    openAuth()
                } else {
                    Snackbar.make(
                        binding.root,
                        R.string.xingsui_account_sync_failed,
                        Snackbar.LENGTH_LONG,
                    ).show()
                }
            }
    }

    private fun renderAccount(user: UserAccount) {
        val isVip = user.vipStatus == VIP_ACTIVE
        binding.profileEmail.text = user.email
        binding.profileAvatar.text = user.email.firstOrNull()?.uppercaseChar()?.toString() ?: "星"
        binding.profileMembership.setText(
            if (isVip) R.string.xingsui_profile_vip else R.string.xingsui_profile_standard
        )
        binding.profileMembership.background = membershipBackground(isVip)
        binding.profileMembership.setTextColor(if (isVip) 0xFF241B05.toInt() else 0xFFD5D8E6.toInt())
        binding.profileExpiry.text = if (isVip) {
            user.vipExpiredAt?.atZone(ZoneId.systemDefault())?.format(DATE_FORMATTER)
                ?: getString(R.string.xingsui_profile_not_active)
        } else {
            getString(R.string.xingsui_profile_not_active)
        }
        binding.profileTraffic.setText(R.string.xingsui_profile_synced)
        binding.profileInviteDetail.text = user.inviteCode
    }

    private fun membershipBackground(isVip: Boolean) = GradientDrawable().apply {
        cornerRadius = resources.displayMetrics.density * 999f
        setColor(if (isVip) 0xFFFFD36A.toInt() else 0x1FFFFFFF)
        if (!isVip) {
            setStroke(resources.displayMetrics.density.toInt().coerceAtLeast(1), 0x2FFFFFFF)
        }
    }

    private fun copyInviteCode() {
        val code = account?.inviteCode ?: sessionStore.load()?.inviteCode ?: return
        val clipboard = getSystemService(ClipboardManager::class.java)
        clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.xingsui_profile_invite), code))
        Snackbar.make(binding.root, R.string.xingsui_invite_copied, Snackbar.LENGTH_SHORT).show()
    }

    private suspend fun checkUpdate() {
        val client = apiClient ?: return
        binding.profileUpdate.isEnabled = false
        runCatching { client.getAppVersion(BuildConfig.VERSION_CODE) }
            .onSuccess { version ->
                if (version.versionCode > BuildConfig.VERSION_CODE) {
                    Snackbar.make(
                        binding.root,
                        getString(R.string.xingsui_profile_new_version, version.versionName),
                        Snackbar.LENGTH_LONG,
                    ).setAction(R.string.xingsui_profile_update_action) {
                        openUri(resolveDownloadUrl(version.downloadUrl))
                    }.show()
                } else {
                    Snackbar.make(binding.root, R.string.xingsui_profile_latest, Snackbar.LENGTH_SHORT).show()
                }
            }
            .onFailure {
                Snackbar.make(binding.root, R.string.xingsui_profile_update_failed, Snackbar.LENGTH_LONG).show()
            }
        binding.profileUpdate.isEnabled = true
    }

    private fun resolveDownloadUrl(downloadUrl: String): String {
        return if (downloadUrl.startsWith("http://") || downloadUrl.startsWith("https://")) {
            downloadUrl
        } else {
            WEBSITE_URL + if (downloadUrl.startsWith("/")) downloadUrl else "/" + downloadUrl
        }
    }

    private fun openUri(url: String) {
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
            .onFailure {
                Snackbar.make(binding.root, R.string.xingsui_api_unavailable, Snackbar.LENGTH_LONG).show()
            }
    }

    private fun logout() {
        sessionStore.clear()
        startActivity(
            Intent(this, XingsuiHomeActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        finish()
    }

    private fun openAuth() {
        startActivity(
            Intent(this, XingsuiAuthActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        )
        finish()
    }

    private fun Throwable.isUnauthorized(): Boolean =
        (this as? XingsuiHttpException)?.isUnauthorized == true ||
            (cause as? XingsuiHttpException)?.isUnauthorized == true

    companion object {
        private const val WEBSITE_URL = "https://xingsui.org"
        private const val VIP_ACTIVE = "active"
        private val DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd")
    }
}
