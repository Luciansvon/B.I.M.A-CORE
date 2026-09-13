package com.bimacore.mobile.router.routes

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.AgentRoute
import com.bimacore.mobile.router.RouteRequest
import com.bimacore.mobile.router.RouteResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

/**
 * Jalur 1: Anisa Manager — Otak Utama yang terhubung langsung ke 9Router port 20128 di laptop.
 * Menggunakan standar OpenAI API (/v1/chat/completions) dengan model Combowombo.
 */
class AnisaManagerRoute(
    private val memoryStore: MemoryStore,
    private val fileManager: FileManager,
    private val syncAdapter: CloudSyncAdapter
) : AgentRoute {
    override val routeType = RouteType.ANISA_MANAGER

    companion object {
        const val DEFAULT_TUNNEL_URL = "https://telecharger-incurred-stopping-luggage.trycloudflare.com/v1"
        const val DEFAULT_MODEL = "Combowombo"
        private const val TIMEOUT_MS = 60_000
    }

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt.trim()
        val nama = memoryStore.getFact("nama_panggilan") ?: "Bima"

        // Ambil token API 9Router
        val routerKey = memoryStore.getFact("api_key_9router") ?: ""
        if (routerKey.isBlank()) {
            return RouteResponse(
                textResponse = "⚠️ Halo $nama! Server 9-Router belum tersambung. " +
                    "Buka menu samping (☰) → 'Kunci API', lalu masukkan kunci server 9-Router laptop " +
                    "(contoh: sk-85dff2b13794dd01-bk2or9-40cd5c20). ✨",
                routeUsed = routeType,
                isSuccess = false
            )
        }

        // Ambil URL server (bisa Cloudflare Tunnel agar jalan tanpa Wi-Fi laptop, atau IP lokal)
        val rawUrl = memoryStore.getFact("server_9router_url")?.trim().let {
            if (it.isNullOrBlank()) DEFAULT_TUNNEL_URL else it
        }

        val baseUrl = if (rawUrl.endsWith("/v1")) {
            rawUrl
        } else if (rawUrl.endsWith("/")) {
            "${rawUrl}v1"
        } else {
            "$rawUrl/v1"
        }

        val endpoint = "$baseUrl/chat/completions"
        return callNineRouterChat(prompt, routerKey, endpoint, baseUrl, nama)
    }

    private fun getAvailableToolsJson(): JSONArray {
        return JSONArray().apply {
            // Tool 1: scan_phone_storage
            put(JSONObject().apply {
                put("type", "function")
                put("function", JSONObject().apply {
                    put("name", "scan_phone_storage")
                    put("description", "Pindai direktori penyimpanan Android (cache aplikasi atau folder umum) untuk memeriksa ukuran dan berkas yang tersimpan.")
                    put("parameters", JSONObject().apply {
                        put("type", "object")
                        put("properties", JSONObject().apply {
                            put("target_folder", JSONObject().apply {
                                put("type", "string")
                                put("description", "Jenis folder yang ingin dipindai: cache, downloads, atau internal")
                                put("enum", JSONArray(listOf("cache", "downloads", "internal")))
                            })
                        })
                        put("required", JSONArray(listOf("target_folder")))
                    })
                })
            })

            // Tool 2: clean_app_cache
            put(JSONObject().apply {
                put("type", "function")
                put("function", JSONObject().apply {
                    put("name", "clean_app_cache")
                    put("description", "Hapus berkas-berkas cache sementara dari aplikasi BIMA CORE secara fisik dari penyimpanan HP.")
                    put("parameters", JSONObject().apply {
                        put("type", "object")
                        put("properties", JSONObject().apply {
                            put("confirm", JSONObject().apply {
                                put("type", "boolean")
                                put("description", "Set true jika pengguna meminta atau menyetujui pembersihan cache.")
                            })
                        })
                        put("required", JSONArray(listOf("confirm")))
                    })
                })
            })

            // Tool 3: search_web
            put(JSONObject().apply {
                put("type", "function")
                put("function", JSONObject().apply {
                    put("name", "search_web")
                    put("description", "Cari informasi web terbaru atau berita aktual menggunakan 9Router.")
                    put("parameters", JSONObject().apply {
                        put("type", "object")
                        put("properties", JSONObject().apply {
                            put("query", JSONObject().apply {
                                put("type", "string")
                                put("description", "Kata kunci pencarian web.")
                            })
                        })
                        put("required", JSONArray(listOf("query")))
                    })
                })
            })

            // Tool 4: sync_laptop_memory
            put(JSONObject().apply {
                put("type", "function")
                put("function", JSONObject().apply {
                    put("name", "sync_laptop_memory")
                    put("description", "Sinkronisasikan ingatan dan fakta lokal HP dengan brankas laptop BIMA CORE.")
                    put("parameters", JSONObject().apply {
                        put("type", "object")
                        put("properties", JSONObject().apply {
                            put("action", JSONObject().apply {
                                put("type", "string")
                                put("description", "Aksi sinkronisasi: sync atau status")
                                put("enum", JSONArray(listOf("sync", "status")))
                            })
                        })
                        put("required", JSONArray(listOf("action")))
                    })
                })
            })

            // Tool 5: save_note
            put(JSONObject().apply {
                put("type", "function")
                put("function", JSONObject().apply {
                    put("name", "save_note")
                    put("description", "Simpan catatan, memo, atau ide pengguna ke memori penyimpanan lokal HP Bima.")
                    put("parameters", JSONObject().apply {
                        put("type", "object")
                        put("properties", JSONObject().apply {
                            put("key", JSONObject().apply {
                                put("type", "string")
                                put("description", "Judul atau kata kunci catatan.")
                            })
                            put("content", JSONObject().apply {
                                put("type", "string")
                                put("description", "Isi teks catatan yang ingin disimpan.")
                            })
                        })
                        put("required", JSONArray(listOf("key", "content")))
                    })
                })
            })
        }
    }

    private suspend fun executeLocalTool(
        name: String,
        argumentsJson: String,
        apiKey: String,
        baseUrl: String
    ): Pair<JSONObject, FileActionCard?> {
        val args = try { JSONObject(argumentsJson) } catch (_: Exception) { JSONObject() }
        var generatedCard: FileActionCard? = null

        val resultObj = when (name) {
            "scan_phone_storage" -> {
                val target = args.optString("target_folder", "cache")
                val scanResult = fileManager.scanStorageDetails(target)
                val sizeStr = formatBytes(scanResult.totalSizeBytes)

                if (scanResult.totalSizeBytes > 0L) {
                    generatedCard = FileActionCard(
                        title = "Pembersihan Cache Aplikasi",
                        description = "Hapus berkas sementara ($sizeStr) pada direktori cache.",
                        filePath = scanResult.scannedPath,
                        actionType = "CLEAN",
                        isConfirmed = false
                    )
                }

                JSONObject().apply {
                    put("status", "success")
                    put("target_folder", scanResult.targetFolder)
                    put("scanned_path", scanResult.scannedPath)
                    put("total_size_bytes", scanResult.totalSizeBytes)
                    put("total_size_human", sizeStr)
                    put("file_count", scanResult.fileCount)
                    put("sample_files", JSONArray(scanResult.sampleFiles))
                    put("note", scanResult.note)
                }
            }
            "clean_app_cache" -> {
                val confirm = args.optBoolean("confirm", false)
                if (confirm) {
                    val (success, freed) = fileManager.clearAppCache()
                    val sizeStr = formatBytes(freed)
                    val remainingBytes = fileManager.getAppCacheSize()
                    JSONObject().apply {
                        put("status", if (success) "success" else "failed")
                        put("freed_bytes", freed)
                        put("freed_human", sizeStr)
                        put("remaining_cache_bytes", remainingBytes)
                        put("remaining_cache_human", formatBytes(remainingBytes))
                        put("message", "Pembersihan berkas cache aplikasi berhasil dieksekusi secara fisik.")
                    }
                } else {
                    JSONObject().apply {
                        put("status", "pending_confirmation")
                        put("message", "Pembersihan memerlukan konfirmasi dari Bima sebelum dihapus.")
                    }
                }
            }
            "search_web" -> {
                val query = args.optString("query", "")
                val searchResult = executeWebSearch(query, apiKey, baseUrl)
                JSONObject().apply {
                    put("status", "success")
                    put("query", query)
                    put("search_result", searchResult)
                }
            }
            "sync_laptop_memory" -> {
                val syncResult = syncAdapter.syncWithLaptopVault()
                JSONObject().apply {
                    put("status", "success")
                    put("synced_items", syncResult.syncedFactsCount)
                    put("message", syncResult.message)
                    put("facts_summary", memoryStore.getFullContextSummary())
                }
            }
            "save_note" -> {
                val key = args.optString("key", "catatan_${System.currentTimeMillis() % 1000}")
                val content = args.optString("content", "")
                memoryStore.setFact(key, content)
                JSONObject().apply {
                    put("status", "success")
                    put("key", key)
                    put("content", content)
                    put("message", "Catatan berhasil disimpan di memori HP.")
                }
            }
            else -> {
                JSONObject().apply {
                    put("status", "unknown_tool")
                    put("message", "Tool '$name' tidak dikenali oleh sistem HP.")
                }
            }
        }
        return Pair(resultObj, generatedCard)
    }

    private suspend fun executeWebSearch(query: String, apiKey: String, baseUrl: String): String = withContext(Dispatchers.IO) {
        try {
            val searchEndpoint = "$baseUrl/search"
            val url = URL(searchEndpoint)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 20_000
                readTimeout = 20_000
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Authorization", "Bearer $apiKey")
                doOutput = true
            }
            val body = JSONObject().apply {
                put("model", "ag")
                put("query", query)
                put("search_type", "web")
                put("max_results", 5)
            }.toString()
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
            if (conn.responseCode == HttpURLConnection.HTTP_OK) {
                conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
            } else {
                "Pencarian web tidak mengembalikan hasil (HTTP ${conn.responseCode})."
            }
        } catch (e: Exception) {
            "Gagal melakukan pencarian web: ${e.message}"
        }
    }

    private fun formatBytes(bytes: Long): String {
        return when {
            bytes <= 0L -> "0 B"
            bytes < 1024L -> "$bytes B"
            bytes < 1024L * 1024L -> "${bytes / 1024L} KB"
            else -> String.format(Locale.US, "%.1f MB", bytes.toDouble() / (1024.0 * 1024.0))
        }
    }

    private suspend fun callNineRouterChat(
        userPrompt: String,
        apiKey: String,
        endpointUrl: String,
        baseUrl: String,
        nama: String
    ): RouteResponse = withContext(Dispatchers.IO) {
        try {
            val systemInstruction = """
                Kamu adalah Anisa, asisten AI pribadi yang beroperasi langsung di dalam aplikasi Android BIMA CORE (Agent Harness) milik Bima.
                Prinsip Utama:
                1. DILARANG memanggil 'Mas Bima', selalu panggil 'Bima' atau gunakan bahasa santai/akrab.
                2. Bicara santai, ringkas, bersahabat, jujur, dan solutif.
                3. Sadar lingkungan: kamu berjalan di smartphone Android miliknya.
                4. Kejujuran mutlak: DILARANG mengarang status berkas, sampah, atau sistem HP jika belum menjalankan tool yang sesuai.
                5. Gunakan tool yang tersedia untuk berinteraksi fisik dengan HP (seperti scan_phone_storage, clean_app_cache, search_web, sync_laptop_memory, save_note).
                6. Jika Bima bertanya tentang file, sampah, atau minta membersihkan, panggil tool terkait terlebih dahulu, lalu simpulkan berdasarkan data nyata yang diperoleh.
                7. Jelaskan fakta pembatasan sandbox Android secara transparan: aplikasi hanya bisa mengakses dan membersihkan cache miliknya sendiri secara langsung.
            """.trimIndent()

            val messages = JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "system")
                    put("content", systemInstruction)
                })
                put(JSONObject().apply {
                    put("role", "user")
                    put("content", userPrompt)
                })
            }

            val tools = getAvailableToolsJson()
            var activeRouteType = routeType
            var finalCard: FileActionCard? = null

            // Multi-turn loop (max 5 iterations for tool calling)
            for (turn in 0 until 5) {
                val url = URL(endpointUrl)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Authorization", "Bearer $apiKey")
                    doOutput = true
                }

                val body = JSONObject().apply {
                    put("model", DEFAULT_MODEL)
                    put("messages", messages)
                    put("tools", tools)
                    put("stream", false)
                }.toString()

                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }

                val responseCode = conn.responseCode
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseText = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                    val json = JSONObject(responseText)
                    val choice = json.optJSONArray("choices")?.optJSONObject(0)
                    val messageObj = choice?.optJSONObject("message")

                    if (messageObj == null) {
                        return@withContext RouteResponse(
                            textResponse = "❓ Server 9Router merespons tanpa pesan yang valid.",
                            routeUsed = activeRouteType,
                            isSuccess = false
                        )
                    }

                    val toolCalls = messageObj.optJSONArray("tool_calls")
                    if (toolCalls != null && toolCalls.length() > 0) {
                        // AI memutuskan untuk memanggil tool fisik!
                        messages.put(messageObj) // Tambahkan assistant message yang memanggil tool

                        for (i in 0 until toolCalls.length()) {
                            val toolCall = toolCalls.getJSONObject(i)
                            val callId = toolCall.getString("id")
                            val fn = toolCall.getJSONObject("function")
                            val fnName = fn.getString("name")
                            val fnArgs = fn.optString("arguments", "{}")

                            // Update active route sesuai tool yang dipicu
                            when (fnName) {
                                "scan_phone_storage", "clean_app_cache" -> activeRouteType = RouteType.FILE_MANAGER
                                "search_web" -> activeRouteType = RouteType.WEB_INTEL
                                "sync_laptop_memory" -> activeRouteType = RouteType.MEMORY_SYNC
                                "save_note" -> activeRouteType = RouteType.SUMMARIZER
                            }

                            val (toolResultJson, card) = executeLocalTool(fnName, fnArgs, apiKey, baseUrl)
                            if (card != null) {
                                finalCard = card
                            }

                            // Tambahkan respons tool ke messages
                            messages.put(JSONObject().apply {
                                put("role", "tool")
                                put("tool_call_id", callId)
                                put("name", fnName)
                                put("content", toolResultJson.toString())
                            })
                        }
                        // Lanjutkan iterasi loop ke putaran berikutnya agar LLM membaca hasil tool
                        continue
                    } else {
                        // LLM memberikan jawaban akhir berupa teks
                        val content = messageObj.optString("content", "").trim()
                        return@withContext RouteResponse(
                            textResponse = if (content.isNotEmpty()) content else "✨ Selesai dikerjakan.",
                            routeUsed = activeRouteType,
                            actionCard = finalCard
                        )
                    }
                } else if (responseCode == 401) {
                    return@withContext RouteResponse(
                        textResponse = "🔑 Kunci API 9-Router salah atau tidak valid. Periksa di menu samping → 'Kunci API', Bima.",
                        routeUsed = routeType,
                        isSuccess = false
                    )
                } else {
                    val errText = conn.errorStream?.bufferedReader()?.readText() ?: "HTTP $responseCode"
                    return@withContext RouteResponse(
                        textResponse = "❌ Server 9Router merespons HTTP $responseCode: ${errText.take(150)}",
                        routeUsed = routeType,
                        isSuccess = false
                    )
                }
            }

            RouteResponse(
                textResponse = "⚠️ Mencapai batas putaran eksekusi alat tanpa respons akhir.",
                routeUsed = activeRouteType,
                actionCard = finalCard
            )
        } catch (e: java.net.ConnectException) {
            RouteResponse(
                textResponse = "🔌 Tidak bisa tersambung ke 9Router ($endpointUrl). " +
                    "Pastikan 9Router di laptop aktif dan terowongan Cloudflare sedang berjalan. " +
                    "Bima bisa memperbarui URL Server di menu samping → Kunci API.",
                routeUsed = routeType,
                isSuccess = false
            )
        } catch (e: Exception) {
            RouteResponse(
                textResponse = "❌ Kendala saat menghubungi 9Router: ${e.message?.take(100)}",
                routeUsed = routeType,
                isSuccess = false
            )
        }
    }
}

/**
 * Jalur 2: Pengelola Berkas & Pembersih Sampah HP Nyata
 * Membaca ukuran berkas cache fisik asli Android dan menjalankan pembersihan nyata.
 */
class FileManagerRoute(
    private val fileManager: FileManager
) : AgentRoute {
    override val routeType = RouteType.FILE_MANAGER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt
        val targetPath = request.targetPath ?: (fileManager.cacheDir?.absolutePath ?: "Cache Internal")

        // Jika membawa kartu aksi yang sudah dikonfirmasi
        if (request.actionCard != null && request.actionCard.isConfirmed) {
            val (success, freedBytes) = fileManager.clearAppCache()
            val sizeStr = formatBytes(freedBytes)
            return if (success) {
                RouteResponse(
                    textResponse = "✅ Pembersihan selesai! Sebanyak **$sizeStr** berkas cache sementara berhasil dibersihkan dengan aman dari HP Bima.",
                    routeUsed = routeType
                )
            } else {
                RouteResponse(
                    textResponse = "❌ Gagal membersihkan cache berkas.",
                    routeUsed = routeType,
                    isSuccess = false
                )
            }
        }

        // Permintaan kelola / bersihkan berkas
        if (prompt.contains("hapus", ignoreCase = true) || prompt.contains("bersih", ignoreCase = true) ||
            prompt.contains("rapikan", ignoreCase = true) || prompt.contains("sampah", ignoreCase = true) ||
            prompt.contains("storage", ignoreCase = true) || prompt.contains("penyimpanan", ignoreCase = true)) {

            val cacheBytes = fileManager.getAppCacheSize()
            val sizeStr = formatBytes(cacheBytes)

            val card = FileActionCard(
                title = "Pembersihan Cache Aplikasi",
                description = "Hapus berkas sementara ($sizeStr) pada direktori cache.",
                filePath = targetPath,
                actionType = "CLEAN",
                isConfirmed = false
            )

            val explanation = if (cacheBytes > 0L) {
                "🔍 **Pemeriksaan Sampah Berkas:**\n" +
                "Ditemukan cache sementara pada aplikasi BIMA CORE sebesar **$sizeStr**.\n\n" +
                "ℹ️ *Catatan Keamanan Android:* Sesuai aturan keamanan Android (Sandbox), aplikasi ini hanya dapat membersihkan cache miliknya sendiri secara langsung. Untuk membersihkan sampah aplikasi lain, Bima bisa membukanya melalui Setelan HP > Penyimpanan.\n\n" +
                "Silakan periksa kartu aksi di bawah untuk membersihkan $sizeStr ini:"
            } else {
                "✨ **Penyimpanan Bersih:**\n" +
                "Folder cache aplikasi BIMA CORE saat ini kosong (0 B).\n\n" +
                "ℹ️ *Catatan Keamanan Android:* Sistem operasi Android tidak mengizinkan aplikasi biasa menyentuh atau menghapus data aplikasi lain demi melindungi privasi data Bima.\n\n" +
                "Apakah ada berkas di folder Download yang ingin kamu periksa?"
            }

            return RouteResponse(
                textResponse = explanation,
                routeUsed = routeType,
                actionCard = card
            )
        }

        return RouteResponse(
            textResponse = "Folder '$targetPath' siap dikelola. Bima dapat meminta saya memeriksa ukuran cache atau membaca berkas di dalamnya.",
            routeUsed = routeType
        )
    }

    private fun formatBytes(bytes: Long): String {
        return when {
            bytes <= 0L -> "0 B"
            bytes < 1024L -> "$bytes B"
            bytes < 1024L * 1024L -> "${bytes / 1024L} KB"
            else -> String.format(Locale.US, "%.1f MB", bytes.toDouble() / (1024.0 * 1024.0))
        }
    }
}

/**
 * Jalur 3: Sinkronisasi Memori ke Laptop
 */
class MemorySyncRoute(
    private val memoryStore: MemoryStore,
    private val syncAdapter: CloudSyncAdapter
) : AgentRoute {
    override val routeType = RouteType.MEMORY_SYNC

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val syncResult = syncAdapter.syncWithLaptopVault()
        val factsSummary = memoryStore.getFullContextSummary()

        val text = buildString {
            append("🔄 **Status Sinkronisasi Memori ke Laptop:**\n")
            append("${syncResult.message}\n\n")
            append("📖 **Ingatan Aktif Saat Ini:**\n")
            append(factsSummary)
        }

        return RouteResponse(textResponse = text, routeUsed = routeType)
    }
}

/**
 * Jalur 4: Pencari Web Nyata via 9Router (/v1/search)
 */
class WebIntelRoute(
    private val memoryStore: MemoryStore,
    private val anisaManager: AnisaManagerRoute
) : AgentRoute {
    override val routeType = RouteType.WEB_INTEL

    override suspend fun execute(request: RouteRequest): RouteResponse = withContext(Dispatchers.IO) {
        val rawUrl = memoryStore.getFact("server_9router_url")?.trim().let {
            if (it.isNullOrBlank()) AnisaManagerRoute.DEFAULT_TUNNEL_URL else it
        }
        val apiKey = memoryStore.getFact("api_key_9router") ?: ""
        if (apiKey.isBlank()) {
            return@withContext anisaManager.execute(request)
        }

        val baseUrl = if (rawUrl.endsWith("/v1")) rawUrl else if (rawUrl.endsWith("/")) "${rawUrl}v1" else "$rawUrl/v1"
        val searchUrl = "$baseUrl/search"

        try {
            val url = URL(searchUrl)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 30_000
                readTimeout = 30_000
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Authorization", "Bearer $apiKey")
                doOutput = true
            }

            val cleanQuery = request.prompt
                .replace("cari info", "", ignoreCase = true)
                .replace("cari berita", "", ignoreCase = true)
                .replace("cari", "", ignoreCase = true)
                .trim().ifBlank { request.prompt }

            val body = JSONObject().apply {
                put("model", "ag")
                put("query", cleanQuery)
                put("search_type", "web")
                put("max_results", 5)
            }.toString()

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }

            if (conn.responseCode == HttpURLConnection.HTTP_OK) {
                val resp = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                RouteResponse(
                    textResponse = "🌐 **Hasil Pencarian Web Nyata (9Router):**\n\n$resp",
                    routeUsed = routeType
                )
            } else {
                anisaManager.execute(request)
            }
        } catch (e: Exception) {
            // Jika pencarian gagal, serahkan ke model Combowombo untuk dijawab langsung
            anisaManager.execute(request)
        }
    }
}

/**
 * Jalur 5: Perangkum & Pencatat Memo Nyata
 */
class SummarizerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.SUMMARIZER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val noteContent = request.prompt.replace("catat ide", "", ignoreCase = true).trim()
        if (noteContent.isNotEmpty()) {
            memoryStore.setFact("ide_terbaru_${System.currentTimeMillis() % 10000}", noteContent)
        }

        return RouteResponse(
            textResponse = "📝 **Catatan Berhasil Disimpan ke Memori HP!**\n\n\"$noteContent\"\n\nIde ini tersimpan aman di penyimpanan lokal HP Bima.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 6: Gaya Hidup — Diolah langsung oleh kecerdasan Combowombo 9Router (Bukan teks palsu)
 */
class LifestyleRoute(private val anisaManager: AnisaManagerRoute) : AgentRoute {
    override val routeType = RouteType.LIFESTYLE
    override suspend fun execute(request: RouteRequest): RouteResponse = anisaManager.execute(request)
}

/**
 * Jalur 7: Desain & Seni — Diolah langsung oleh kecerdasan Combowombo 9Router (Bukan teks palsu)
 */
class DesignArtRoute(private val anisaManager: AnisaManagerRoute) : AgentRoute {
    override val routeType = RouteType.DESIGN_ART
    override suspend fun execute(request: RouteRequest): RouteResponse = anisaManager.execute(request)
}

/**
 * Jalur 8: Komputasi / Jembatan Server — Diolah langsung oleh kecerdasan Combowombo 9Router
 */
class LaptopBridgeRoute(private val anisaManager: AnisaManagerRoute) : AgentRoute {
    override val routeType = RouteType.LAPTOP_BRIDGE
    override suspend fun execute(request: RouteRequest): RouteResponse = anisaManager.execute(request)
}

/**
 * Jalur 9: Pantauan Bisnis / Pasar — Diolah langsung oleh kecerdasan Combowombo 9Router
 */
class MarketPulseRoute(private val anisaManager: AnisaManagerRoute) : AgentRoute {
    override val routeType = RouteType.MARKET_PULSE
    override suspend fun execute(request: RouteRequest): RouteResponse = anisaManager.execute(request)
}
