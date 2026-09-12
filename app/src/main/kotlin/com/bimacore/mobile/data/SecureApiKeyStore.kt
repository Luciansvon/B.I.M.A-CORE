package com.bimacore.mobile.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Stores API keys encrypted at rest using a non-exportable Android Keystore key.
 * Only encrypted ciphertext + IV are kept in SharedPreferences.
 */
class SecureApiKeyStore(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun put(provider: String, apiKey: String) {
        val normalizedProvider = normalizeProvider(provider)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())

        val ciphertext = cipher.doFinal(apiKey.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString("${normalizedProvider}_iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("${normalizedProvider}_ciphertext", Base64.encodeToString(ciphertext, Base64.NO_WRAP))
            .apply()
    }

    fun get(provider: String): String? {
        val normalizedProvider = normalizeProvider(provider)
        val encodedIv = prefs.getString("${normalizedProvider}_iv", null) ?: return null
        val encodedCiphertext = prefs.getString("${normalizedProvider}_ciphertext", null) ?: return null

        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            val iv = Base64.decode(encodedIv, Base64.NO_WRAP)
            val ciphertext = Base64.decode(encodedCiphertext, Base64.NO_WRAP)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(), GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv))
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (_: Exception) {
            // A restored/corrupted ciphertext cannot be decrypted with a different device key.
            remove(normalizedProvider)
            null
        }
    }

    fun remove(provider: String) {
        val normalizedProvider = normalizeProvider(provider)
        prefs.edit()
            .remove("${normalizedProvider}_iv")
            .remove("${normalizedProvider}_ciphertext")
            .apply()
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()

        keyGenerator.init(spec)
        return keyGenerator.generateKey()
    }

    private fun normalizeProvider(provider: String): String = provider.trim().lowercase()

    private companion object {
        const val PREFS_NAME = "bima_core_secure_api_keys"
        const val KEY_ALIAS = "bima_core_api_key_encryption_v1"
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val GCM_TAG_LENGTH_BITS = 128
    }
}
