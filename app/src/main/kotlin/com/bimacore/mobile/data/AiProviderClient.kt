package com.bimacore.mobile.data

import com.bimacore.mobile.model.RouteType
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.net.HttpURLConnection
import java.net.URL

class AiProviderClient(
    private val secretStore: SecureApiKeyStore
) {

    private val json = Json { ignoreUnknownKeys = true }

    fun hasAnyKey(): Boolean =
        !secretStore.get("openrouter").isNullOrBlank() || !secretStore.get("gemini").isNullOrBlank()

    suspend fun generate(routeType: RouteType, prompt: String): Result<String> = withContext(Dispatchers.IO) {
        try {
            val openRouterKey = secretStore.get("openrouter")
            if (!openRouterKey.isNullOrBlank()) {
                return@withContext Result.success(callOpenRouter(openRouterKey, routeType, prompt))
            }

            val geminiKey = secretStore.get("gemini")
            if (!geminiKey.isNullOrBlank()) {
                return@withContext Result.success(callGemini(geminiKey, routeType, prompt))
            }

            Result.failure(IllegalStateException("Kunci API belum dikonfigurasi"))
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    private fun callOpenRouter(apiKey: String, routeType: RouteType, prompt: String): String {
        val body = buildJsonObject {
            put("model", "openrouter/auto")
            put("messages", buildJsonArray {
                add(buildJsonObject {
                    put("role", "system")
                    put("content", systemPrompt(routeType))
                })
                add(buildJsonObject {
                    put("role", "user")
                    put("content", prompt)
                })
            })

            if (requiresFreshWeb(routeType)) {
                put("plugins", buildJsonArray {
                    add(buildJsonObject { put("id", "web") })
                })
            }
        }.toString()

        val response = executeJsonPost(
            url = OPENROUTER_URL,
            body = body,
            headers = mapOf(
                "Authorization" to "Bearer $apiKey",
                "HTTP-Referer" to "https://github.com/Luciansvon/B.I.M.A-CORE",
                "X-Title" to "BIMA CORE Mobile"
            )
        )

        val root = json.parseToJsonElement(response).jsonObject
        val content = root["choices"]
            ?.jsonArray
            ?.firstOrNull()
            ?.jsonObject
            ?.get("message")
            ?.jsonObject
            ?.get("content")
            ?.jsonPrimitive
            ?.contentOrNull
            ?.trim()

        return content?.takeIf { it.isNotEmpty() }
            ?: error("OpenRouter mengembalikan respons kosong")
    }

    private fun callGemini(apiKey: String, routeType: RouteType, prompt: String): String {
        val body = buildJsonObject {
            put("systemInstruction", buildJsonObject {
                put("parts", buildJsonArray {
                    add(buildJsonObject { put("text", systemPrompt(routeType)) })
                })
            })
            put("contents", buildJsonArray {
                add(buildJsonObject {
                    put("role", "user")
                    put("parts", buildJsonArray {
                        add(buildJsonObject { put("text", prompt) })
                    })
                })
            })

            if (requiresFreshWeb(routeType)) {
                put("tools", buildJsonArray {
                    add(buildJsonObject {
                        put("googleSearch", buildJsonObject { })
                    })
                })
            }
        }.toString()

        val response = executeJsonPost(
            url = GEMINI_URL,
            body = body,
            headers = mapOf("x-goog-api-key" to apiKey)
        )

        val root = json.parseToJsonElement(response).jsonObject
        val parts = root["candidates"]
            ?.jsonArray
            ?.firstOrNull()
            ?.jsonObject
            ?.get("content")
            ?.jsonObject
            ?.get("parts")
            ?.jsonArray
            .orEmpty()

        val text = parts.mapNotNull { part ->
            part.jsonObject["text"]?.jsonPrimitive?.contentOrNull
        }.joinToString(separator = "").trim()

        return text.takeIf { it.isNotEmpty() }
            ?: error("Gemini mengembalikan respons kosong")
    }

    private fun executeJsonPost(
        url: String,
        body: String,
        headers: Map<String, String>
    ): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = "POST"
            connection.connectTimeout = CONNECT_TIMEOUT_MS
            connection.readTimeout = READ_TIMEOUT_MS
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.setRequestProperty("Accept", "application/json")
            headers.forEach { (name, value) -> connection.setRequestProperty(name, value) }

            connection.outputStream.bufferedWriter(Charsets.UTF_8).use { writer ->
                writer.write(body)
            }

            val status = connection.responseCode
            val responseStream = if (status in 200..299) connection.inputStream else connection.errorStream
            val responseText = responseStream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()

            if (status !in 200..299) {
                error("Provider AI gagal (HTTP $status): ${responseText.take(MAX_ERROR_BODY_CHARS)}")
            }

            responseText
        } finally {
            connection.disconnect()
        }
    }

    private fun systemPrompt(routeType: RouteType): String = buildString {
        append("Kamu adalah Anisa di BIMA CORE Mobile. Jawab dalam Bahasa Indonesia yang ringkas, jelas, dan praktis. ")
        append("Rute aktif: ${routeType.label}. ")
        append("Jangan mengaku sudah menjalankan aksi perangkat, sinkronisasi, file operation, atau remote laptop jika aplikasi belum benar-benar melakukannya. ")
        if (requiresFreshWeb(routeType)) {
            append("Gunakan hasil pencarian web yang tersedia dan jangan mengarang data terbaru.")
        }
    }

    private fun requiresFreshWeb(routeType: RouteType): Boolean = when (routeType) {
        RouteType.WEB_INTEL,
        RouteType.LIFESTYLE,
        RouteType.MARKET_PULSE -> true
        else -> false
    }

    private companion object {
        const val OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
        const val GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
        const val CONNECT_TIMEOUT_MS = 15_000
        const val READ_TIMEOUT_MS = 45_000
        const val MAX_ERROR_BODY_CHARS = 600
    }
}
