package org.amnezia.awg.xingsui

import android.content.Context

data class AuthSession(
    val accessToken: String,
    val userId: String,
    val email: String,
    val inviteCode: String,
)

class XingsuiSessionStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun load(): AuthSession? {
        val accessToken = preferences.getString(KEY_ACCESS_TOKEN, null) ?: return null
        val userId = preferences.getString(KEY_USER_ID, null) ?: return null
        val email = preferences.getString(KEY_EMAIL, null) ?: return null
        val inviteCode = preferences.getString(KEY_INVITE_CODE, null) ?: return null
        return AuthSession(accessToken, userId, email, inviteCode)
    }

    fun save(session: AuthSession) {
        preferences.edit()
            .putString(KEY_ACCESS_TOKEN, session.accessToken)
            .putString(KEY_USER_ID, session.userId)
            .putString(KEY_EMAIL, session.email)
            .putString(KEY_INVITE_CODE, session.inviteCode)
            .apply()
    }

    fun clear() {
        preferences.edit().clear().apply()
    }

    companion object {
        private const val PREFERENCES_NAME = "xingsui_session"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_EMAIL = "email"
        private const val KEY_INVITE_CODE = "invite_code"
    }
}
