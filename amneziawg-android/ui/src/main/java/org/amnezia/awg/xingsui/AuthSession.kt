package org.amnezia.awg.xingsui

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class AuthSession(
    val accessToken: String,
    val userId: String,
    val email: String,
    val inviteCode: String,
)

class XingsuiSessionStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    @Synchronized
    fun load(): AuthSession? {
        val accessToken = loadEncryptedAccessToken() ?: return null
        val userId = preferences.getString(KEY_USER_ID, null) ?: return null
        val email = preferences.getString(KEY_EMAIL, null) ?: return null
        val inviteCode = preferences.getString(KEY_INVITE_CODE, null) ?: return null
        return AuthSession(accessToken, userId, email, inviteCode)
    }

    @Synchronized
    fun save(session: AuthSession) {
        val encrypted = encrypt(session.accessToken)
        check(preferences.edit()
            .putString(KEY_ACCESS_TOKEN_CIPHERTEXT, encrypted.ciphertext)
            .putString(KEY_ACCESS_TOKEN_IV, encrypted.iv)
            .putString(KEY_USER_ID, session.userId)
            .putString(KEY_EMAIL, session.email)
            .putString(KEY_INVITE_CODE, session.inviteCode)
            .remove(KEY_ACCESS_TOKEN)
            .commit()) { "Unable to persist encrypted session" }
    }

    @Synchronized
    fun clear() {
        preferences.edit().clear().commit()
        runCatching {
            keyStore().deleteEntry(KEYSTORE_ALIAS)
        }
    }

    private fun loadEncryptedAccessToken(): String? {
        val ciphertext = preferences.getString(KEY_ACCESS_TOKEN_CIPHERTEXT, null)
        val iv = preferences.getString(KEY_ACCESS_TOKEN_IV, null)
        if (ciphertext != null && iv != null) {
            val token = runCatching { decrypt(ciphertext, iv) }.getOrElse {
                clear()
                return null
            }
            if (!preferences.edit().remove(KEY_ACCESS_TOKEN).commit()) {
                clear()
                return null
            }
            return token
        }

        val legacyToken = preferences.getString(KEY_ACCESS_TOKEN, null) ?: run {
            if (ciphertext != null || iv != null) clear()
            return null
        }
        return runCatching {
            val encrypted = encrypt(legacyToken)
            check(preferences.edit()
                .putString(KEY_ACCESS_TOKEN_CIPHERTEXT, encrypted.ciphertext)
                .putString(KEY_ACCESS_TOKEN_IV, encrypted.iv)
                .remove(KEY_ACCESS_TOKEN)
                .commit()) { "Unable to migrate encrypted session" }
            legacyToken
        }.getOrElse {
            clear()
            null
        }
    }

    private fun encrypt(value: String): EncryptedValue {
        val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        cipher.updateAAD(AAD)
        return EncryptedValue(
            ciphertext = Base64.encodeToString(cipher.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP),
            iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP),
        )
    }

    private fun decrypt(ciphertext: String, iv: String): String {
        val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            getOrCreateSecretKey(),
            GCMParameterSpec(GCM_TAG_LENGTH_BITS, Base64.decode(iv, Base64.NO_WRAP)),
        )
        cipher.updateAAD(AAD)
        return cipher.doFinal(Base64.decode(ciphertext, Base64.NO_WRAP)).toString(Charsets.UTF_8)
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val store = keyStore()
        (store.getKey(KEYSTORE_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE).run {
            init(
                KeyGenParameterSpec.Builder(
                    KEYSTORE_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setRandomizedEncryptionRequired(true)
                    .build()
            )
            generateKey()
        }
    }

    private fun keyStore(): KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private data class EncryptedValue(val ciphertext: String, val iv: String)

    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val CIPHER_TRANSFORMATION = "AES/GCM/NoPadding"
        private const val GCM_TAG_LENGTH_BITS = 128
        private const val KEYSTORE_ALIAS = "xingsui.session.access-token.v1"
        private val AAD = "xingsui-access-token-v1".toByteArray(Charsets.UTF_8)
        private const val PREFERENCES_NAME = "xingsui_session"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_ACCESS_TOKEN_CIPHERTEXT = "access_token_ciphertext_v1"
        private const val KEY_ACCESS_TOKEN_IV = "access_token_iv_v1"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_EMAIL = "email"
        private const val KEY_INVITE_CODE = "invite_code"
    }
}
