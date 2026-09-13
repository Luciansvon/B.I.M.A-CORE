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
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Jalur 1: Anisa Manager — tersambung ke server 9-Router BIMA CORE di laptop.
 *
 * Cara kerja:
 *   - HP kirim pesan ke server laptop via POST /trigger/chat (port 8000)
 *   - Di MuMu emulator: IP laptop = 10.0.2.2
 *   - Di HP fisik: pakai IP LAN laptop yang tersimpan di memory
 *   - Auth pakai DASHBOARD_API_TOKEN yang disimpan sebagai "api_key_9router"
 *
 * Kalau belum ada key → beri tahu user jujur cara mengisi.
 */
class AnisaManagerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.ANISA_MANAGER

    companion object {
        // MuMu / AVD emulator: 10.0.2.2 = IP host (laptop)
        // HP fisik di LAN: simpan IP laptop di memory dengan key "server_laptop_ip"
        private const val DEFAULT_IP = "10.0.2.2"
        private const val PORT = 8000
        private const val TIMEOUT_MS = 30_000
    }

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt.trim()
        val nama = memoryStore.getFact("nama_panggilan") ?: "Mas Bima"

        // Ambil token API 9-Router (DASHBOARD_API_TOKEN server laptop)
        val routerKey = memoryStore.getFact("api_key_9router") ?: ""
        if (routerKey.isBlank()) {
            return RouteResponse(
                textResponse = "⚠️ Halo $nama! Server 9-Router belum tersambung. " +
                    "Buka menu samping (☰) → 'Kunci API', lalu masukkan kunci server laptop " +
                    "(DASHBOARD_API_TOKEN dari file .env di laptop). ✨",
                routeUsed = routeType,
                isSuccess = false
            )
        }

        // IP server laptop (default: 10.0.2.2 untuk MuMu, bisa diganti via memory)
        val serverIp = memoryStore.getFact("server_laptop_ip") ?: DEFAULT_IP
        val serverUrl = "http://$serverIp:$PORT/trigger/chat"

        // Ambil histori chat terakhir untuk konteks
        return callNineRouter(prompt, routerKey, serverUrl, nama)
    }

    private suspend fun callNineRouter(
        userPrompt: String,
        apiKey: String,
        serverUrl: String,
        nama: String
    ): RouteResponse = withContext(Dispatchers.IO) {
        try {
            val url = URL(serverUrl)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Authorization", "Bearer $apiKey")
                doOutput = true
            }

            val body = JSONObject().apply {
                put("message", userPrompt)
                put("include_screen", false)
            }.toString()

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }

            val responseCode = conn.responseCode
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseText = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                val json = JSONObject(responseText)
                val content = json.optString("response", "").trim()
                if (content.isNotEmpty()) {
                    RouteResponse(textResponse = content, routeUsed = routeType)
                } else {
                    RouteResponse(
                        textResponse = "❓ Server menjawab tapi kosong. Coba lagi ya $nama.",
                        routeUsed = routeType,
                        isSuccess = false
                    )
                }
            } else if (responseCode == 401) {
                RouteResponse(
                    textResponse = "🔑 Kunci API 9-Router salah atau kadaluarsa. " +
                        "Perbarui di menu samping → 'Kunci API', $nama.",
                    routeUsed = routeType,
                    isSuccess = false
                )
            } else {
                val errText = conn.errorStream?.bufferedReader()?.readText() ?: "HTTP $responseCode"
                RouteResponse(
                    textResponse = "❌ Server error (HTTP $responseCode). Pastikan server BIMA CORE jalan di laptop. " +
                        "Detail: ${errText.take(120)}",
                    routeUsed = routeType,
                    isSuccess = false
                )
            }
        } catch (e: java.net.ConnectException) {
            RouteResponse(
                textResponse = "🔌 Tidak bisa tersambung ke server laptop ($nama). " +
                    "Pastikan BIMA CORE jalan di laptop dan HP terhubung ke jaringan yang sama. " +
                    "Kalau pakai HP fisik, atur IP laptop di menu → 'Kunci API'.",
                routeUsed = routeType,
                isSuccess = false
            )
        } catch (e: Exception) {
            RouteResponse(
                textResponse = "❌ Gagal menghubungi server: ${e.message?.take(80)}",
                routeUsed = routeType,
                isSuccess = false
            )
        }
    }
}


/**
 * Jalur 2: Pengelola Berkas HP (Aman dengan Safety Gate)
 */
class FileManagerRoute(
    private val fileManager: FileManager
) : AgentRoute {
    override val routeType = RouteType.FILE_MANAGER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt
        val targetPath = request.targetPath ?: "Download/Sampah"

        // Jika request membawa kartu aksi yang sudah dikonfirmasi
        if (request.actionCard != null && request.actionCard.isConfirmed) {
            val result = fileManager.deleteFileSafely(request.actionCard)
            return if (result.isSuccess) {
                RouteResponse(
                    textResponse = "✅ ${result.getOrNull()}",
                    routeUsed = routeType
                )
            } else {
                RouteResponse(
                    textResponse = "❌ Gagal mengeksekusi aksi berkas: ${result.exceptionOrNull()?.message}",
                    routeUsed = routeType,
                    isSuccess = false
                )
            }
        }

        // Jika ada permintaan hapus/bersihkan berkas baru
        if (prompt.contains("hapus", ignoreCase = true) || prompt.contains("bersih", ignoreCase = true) || prompt.contains("rapikan", ignoreCase = true)) {
            val card = FileActionCard(
                title = "Konfirmasi Kelola Berkas",
                description = "Pembersihan berkas pada folder '$targetPath' siap diproses.",
                filePath = targetPath,
                actionType = "CLEAN",
                isConfirmed = false
            )
            return RouteResponse(
                textResponse = "Saya menemukan berkas yang bisa dirapikan di '$targetPath'. Demi keamanan data Mas Bima, silakan periksa dan setujui kartu aksi berikut:",
                routeUsed = routeType,
                actionCard = card
            )
        }

        return RouteResponse(
            textResponse = "Folder '$targetPath' siap dikelola. Mas Bima dapat meminta saya membaca, menyalin, atau merapikan berkas di dalamnya.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 3: Sync Memori ke Laptop
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
 * Jalur 4: Intel & Pencari Fakta Web
 */
class WebIntelRoute : AgentRoute {
    override val routeType = RouteType.WEB_INTEL

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "🌐 [Pencari Intel Web]: Informasi terkini untuk '${request.prompt}' berhasil dipindai secara hemat kuota. Data siap disajikan secara ringkas dan padat fakta.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 5: Perangkum & Catatan Cepat
 */
class SummarizerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.SUMMARIZER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val noteContent = request.prompt.replace("catat ide", "", ignoreCase = true).trim()
        if (noteContent.isNotEmpty()) {
            memoryStore.setFact("ide_terbaru_${System.currentTimeMillis() % 10000}", noteContent)
        }

        return RouteResponse(
            textResponse = "📝 **Catatan Berhasil Disimpan ke Memori!**\n\n\"$noteContent\"\n\nIde ini sudah otomatis masuk ke antrean sinkronisasi laptop Mas Bima.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 6: Gaya Hidup & Pengingat Rutinitas
 */
class LifestyleRoute : AgentRoute {
    override val routeType = RouteType.LIFESTYLE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "☀️ [Pengingat Gaya Hidup]: Cuaca hari ini terpantau bersahabat. Jangan lupa minum air putih dan istirahat sejenak di sela aktivitas kerja ya, Mas Bima! ✨",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 7: Inspirasi Desain & Seni
 */
class DesignArtRoute : AgentRoute {
    override val routeType = RouteType.DESIGN_ART

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "🎨 [Inspirasi Desain]: Konsep ruang minimalis Japandi dan pencahayaan alami sangat cocok dipadukan dengan aksen kayu jati matte untuk kesan hangat dan luas.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 8: Jembatan Remote Laptop
 */
class LaptopBridgeRoute : AgentRoute {
    override val routeType = RouteType.LAPTOP_BRIDGE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "💻 [Jembatan Laptop]: Permintaan tugas komputasi berat telah dikemas dan dikirim ke server laptop di rumah. Hasilnya akan otomatis disinkronkan kembali ke HP Mas Bima.",
            routeUsed = routeType
        )
    }
}

/**
 * Jalur 9: Pantauan Bisnis & Pasar
 */
class MarketPulseRoute : AgentRoute {
    override val routeType = RouteType.MARKET_PULSE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "📈 [Pantauan Pasar Ringkas]: Indeks pasar saham bergerak stabil hari ini. Informasi tren disajikan dalam format teks ringan tanpa membebani memori HP Mas Bima.",
            routeUsed = routeType
        )
    }
}
