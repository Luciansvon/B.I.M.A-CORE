package com.bimacore.mobile.router.routes

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.AgentRoute
import com.bimacore.mobile.router.RouteRequest
import com.bimacore.mobile.router.RouteResponse

/** Jalur 1: Anisa Manager. */
class AnisaManagerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.ANISA_MANAGER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt.trim()
        val nama = memoryStore.getFact("nama_panggilan") ?: "Mas Bima"

        val reply = when {
            prompt.contains("halo", ignoreCase = true) || prompt.contains("hai", ignoreCase = true) ->
                "Halo $nama! ✨ Sembilan rute lokal sudah terdaftar. Fitur online hanya berjalan jika provider dan kredensialnya tersedia."

            prompt.contains("siapa kamu", ignoreCase = true) || prompt.contains("anisa", ignoreCase = true) ->
                "Saya Anisa, asisten di BIMA CORE Mobile. Saya mengatur rute lokal dan memakai provider AI online jika sudah dikonfigurasi."

            else ->
                "Saya mengerti, $nama. Mode lokal aktif. Untuk jawaban AI yang lebih luas, simpan kredensial provider dari menu pengaturan."
        }

        return RouteResponse(textResponse = reply, routeUsed = routeType)
    }
}

/** Jalur 2: Pengelola Berkas HP dengan Safety Gate. */
class FileManagerRoute(
    private val fileManager: FileManager
) : AgentRoute {
    override val routeType = RouteType.FILE_MANAGER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt
        val targetPath = request.targetPath ?: "Download/Sampah"

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

        if (
            prompt.contains("hapus", ignoreCase = true) ||
            prompt.contains("bersih", ignoreCase = true) ||
            prompt.contains("rapikan", ignoreCase = true)
        ) {
            val card = FileActionCard(
                title = "Konfirmasi Kelola Berkas",
                description = "Pembersihan berkas pada folder '$targetPath' siap diproses.",
                filePath = targetPath,
                actionType = "CLEAN",
                isConfirmed = false
            )
            return RouteResponse(
                textResponse = "Permintaan pembersihan '$targetPath' membutuhkan konfirmasi eksplisit sebelum eksekusi.",
                routeUsed = routeType,
                actionCard = card
            )
        }

        return RouteResponse(
            textResponse = "File manager lokal aktif. Akses folder eksternal luas tidak diberikan otomatis; gunakan lokasi yang memang dapat diakses aplikasi.",
            routeUsed = routeType
        )
    }
}

/** Jalur 3: Sync Memori ke Laptop. */
class MemorySyncRoute(
    private val memoryStore: MemoryStore,
    private val syncAdapter: CloudSyncAdapter
) : AgentRoute {
    override val routeType = RouteType.MEMORY_SYNC

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val syncResult = syncAdapter.syncWithLaptopVault()
        val factsSummary = memoryStore.getFullContextSummary()

        val text = buildString {
            append("🔄 **Status Sinkronisasi Memori:**\n")
            append("${syncResult.message}\n\n")
            append("📖 **Ingatan Lokal Saat Ini:**\n")
            append(factsSummary)
        }

        return RouteResponse(
            textResponse = text,
            routeUsed = routeType,
            isSuccess = syncResult.isSuccess
        )
    }
}

/** Jalur 4: Intel & Pencari Fakta Web. */
class WebIntelRoute : AgentRoute {
    override val routeType = RouteType.WEB_INTEL

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "🌐 Pencarian web belum dijalankan dalam mode lokal. Konfigurasikan provider AI agar rute ini dapat mengambil data online secara nyata.",
            routeUsed = routeType,
            isSuccess = false
        )
    }
}

/** Jalur 5: Perangkum & Catatan Cepat. */
class SummarizerRoute(private val memoryStore: MemoryStore) : AgentRoute {
    override val routeType = RouteType.SUMMARIZER

    override suspend fun execute(request: RouteRequest): RouteResponse {
        val prompt = request.prompt.trim()
        val isReadRequest = prompt.contains("tampilkan", ignoreCase = true) ||
            prompt.contains("ringkasan", ignoreCase = true) ||
            prompt.contains("lihat", ignoreCase = true)

        if (isReadRequest) {
            return RouteResponse(
                textResponse = "📝 **Ringkasan Memori Lokal:**\n\n${memoryStore.getFullContextSummary()}",
                routeUsed = routeType
            )
        }

        val noteContent = prompt.replace("catat ide", "", ignoreCase = true).trim()
        if (noteContent.isEmpty()) {
            return RouteResponse(
                textResponse = "📝 Tidak ada isi catatan yang diberikan.",
                routeUsed = routeType,
                isSuccess = false
            )
        }

        memoryStore.setFact("ide_terbaru_${System.currentTimeMillis() % 10000}", noteContent)
        return RouteResponse(
            textResponse = "📝 Catatan tersimpan ke memori lokal:\n\n\"$noteContent\"",
            routeUsed = routeType
        )
    }
}

/** Jalur 6: Gaya Hidup & Pengingat Rutinitas. */
class LifestyleRoute : AgentRoute {
    override val routeType = RouteType.LIFESTYLE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "☀️ Data cuaca atau kondisi terbaru belum diambil dalam mode lokal. Aktifkan provider AI online untuk informasi real-time.",
            routeUsed = routeType,
            isSuccess = false
        )
    }
}

/** Jalur 7: Inspirasi Desain & Seni. */
class DesignArtRoute : AgentRoute {
    override val routeType = RouteType.DESIGN_ART

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "🎨 Mode desain lokal siap untuk ide dasar. Provider AI online dapat dipakai untuk respons yang lebih kontekstual.",
            routeUsed = routeType
        )
    }
}

/** Jalur 8: Jembatan Remote Laptop. */
class LaptopBridgeRoute : AgentRoute {
    override val routeType = RouteType.LAPTOP_BRIDGE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "💻 Jembatan laptop belum dikonfigurasi pada build ini. Tidak ada tugas yang dikirim ke perangkat lain.",
            routeUsed = routeType,
            isSuccess = false
        )
    }
}

/** Jalur 9: Pantauan Bisnis & Pasar. */
class MarketPulseRoute : AgentRoute {
    override val routeType = RouteType.MARKET_PULSE

    override suspend fun execute(request: RouteRequest): RouteResponse {
        return RouteResponse(
            textResponse = "📈 Data pasar real-time belum diambil dalam mode lokal. Aktifkan provider AI online untuk pencarian terbaru.",
            routeUsed = routeType,
            isSuccess = false
        )
    }
}
