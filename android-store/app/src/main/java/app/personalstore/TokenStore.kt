package app.personalstore

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** GitHub 토큰을 기기 안에서 암호화해 저장한다. */
class TokenStore(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context,
        "secure_prefs",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    var token: String?
        get() = prefs.getString(KEY, null)
        set(value) = prefs.edit().apply {
            if (value == null) remove(KEY) else putString(KEY, value)
        }.apply()

    var lastNotifiedSignature: String?
        get() = prefs.getString(NOTIFIED, null)
        set(value) = prefs.edit().putString(NOTIFIED, value).apply()

    private companion object {
        const val KEY = "github_token"
        const val NOTIFIED = "last_notified"
    }
}
