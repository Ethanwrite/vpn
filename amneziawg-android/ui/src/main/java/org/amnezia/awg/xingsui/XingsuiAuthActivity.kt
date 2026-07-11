package org.amnezia.awg.xingsui

import android.content.Intent
import android.os.Bundle
import android.util.Patterns
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.launch
import org.amnezia.awg.R
import org.amnezia.awg.databinding.XingsuiAuthActivityBinding
import org.amnezia.awg.xingsui.api.XingsuiApiClient
import org.amnezia.awg.xingsui.api.XingsuiHttpException
import java.io.IOException

class XingsuiAuthActivity : AppCompatActivity() {
    private val apiClient = XingsuiApiClient()
    private lateinit var binding: XingsuiAuthActivityBinding
    private lateinit var sessionStore: XingsuiSessionStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = XingsuiAuthActivityBinding.inflate(layoutInflater)
        sessionStore = XingsuiSessionStore(this)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.loginButton.setOnClickListener { submit(isRegister = false) }
        binding.registerButton.setOnClickListener { submit(isRegister = true) }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun submit(isRegister: Boolean) {
        val email = binding.email.text?.toString()?.trim().orEmpty()
        val password = binding.password.text?.toString().orEmpty()
        val inviteCode = binding.inviteCode.text?.toString()?.trim().orEmpty()
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            binding.email.error = getString(R.string.xingsui_email_invalid)
            return
        }
        if (password.length < MIN_PASSWORD_LENGTH) {
            binding.password.error = getString(R.string.xingsui_password_invalid)
            return
        }

        setLoading(true)
        lifecycleScope.launch {
            runCatching {
                val session = if (isRegister) {
                    apiClient.register(email, password, inviteCode.ifBlank { null })
                } else {
                    apiClient.login(email, password)
                }
                sessionStore.save(session)
                session
            }.onSuccess {
                Snackbar.make(binding.root, R.string.xingsui_auth_success, Snackbar.LENGTH_SHORT).show()
                startActivity(Intent(this@XingsuiAuthActivity, XingsuiHomeActivity::class.java))
                finish()
            }.onFailure {
                setLoading(false)
                XingsuiCrashReporter.recordException("auth-submit", it)
                Snackbar.make(binding.root, authErrorMessage(it, isRegister), Snackbar.LENGTH_LONG).show()
            }
        }
    }

    private fun authErrorMessage(error: Throwable, isRegister: Boolean): String {
        return when (error) {
            is XingsuiHttpException -> when (error.statusCode) {
                401 -> getString(R.string.xingsui_auth_invalid_credentials)
                409 -> getString(R.string.xingsui_auth_email_exists)
                422 -> getString(R.string.xingsui_auth_invalid_request)
                in 500..599 -> getString(R.string.xingsui_auth_server_failed)
                else -> getString(R.string.xingsui_auth_failed)
            }
            is IOException -> getString(R.string.xingsui_auth_network_failed)
            else -> {
                val message = error.message.orEmpty()
                if (message.contains("网络连接失败")) {
                    getString(R.string.xingsui_auth_network_failed)
                } else if (isRegister) {
                    getString(R.string.xingsui_auth_register_failed)
                } else {
                    getString(R.string.xingsui_auth_failed)
                }
            }
        }
    }

    private fun setLoading(isLoading: Boolean) {
        binding.loginButton.isEnabled = !isLoading
        binding.registerButton.isEnabled = !isLoading
        binding.email.isEnabled = !isLoading
        binding.password.isEnabled = !isLoading
        binding.inviteCode.isEnabled = !isLoading
    }

    companion object {
        private const val MIN_PASSWORD_LENGTH = 6
    }
}
