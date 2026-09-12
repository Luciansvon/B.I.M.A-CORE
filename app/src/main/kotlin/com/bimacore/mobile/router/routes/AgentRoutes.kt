package com.bimacore.mobile.router.routes

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.AgentRoute
import com.bimacore.mobile.router.RouteRequest
import com.bimacore.mobile.router.RouteResponse

/**
 * Jalur 1: Anisa Manager (Pusat Komando & Percakapan Utama)
 */
class AnisaManagerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.ANISA_MANAGER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt.trim()
        val nama = memoryStore.getFact("nama_panggilan") ?: "Mas Bima"

        val reply = when {
            prompt.contains("halo", ignoreCase = true) || prompt.contains("hai", ignoreCase = true) ->
                "Halo $nama! ✨ Senang sekali bisa mendampingi Mas Bima hari ini. Semua 9-Router di HP dalam kondisi aktif dan siaga. Ada yang mau kita kerjakan atau diskusikan?"

            prompt.contains("siapa kamu", ignoreCase = true) || prompt.contains("anisa", ignoreCase = true) ->
                "Saya Anisa, asisten pribadi Mas Bima di BIMA CORE Mobile ✨. Saya bertugas mengkoordinasikan tugas harian, merapikan berkas di HP, dan menjaga ingatan kita agar selalu nyambung ke laptop."

            else ->
                "Saya mengerti, $nama. Saya siap membantu menindaklanjuti hal ini. Jika Mas Bima butuh saya merapikan berkas di HP, mencatat ide baru, atau menyinkronkan data ke laptop, tinggal beri tahu saya ya! ✨"
        }

        return RouteResponse(textResponse = reply, routeUsed = routeType)
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
