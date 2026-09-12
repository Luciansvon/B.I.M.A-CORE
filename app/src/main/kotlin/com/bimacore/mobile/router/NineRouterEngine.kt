package com.bimacore.mobile.router

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.RouteStatus
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.routes.*

class NineRouterEngine(
    private val memoryStore: MemoryStore,
    private val fileManager: FileManager,
    private val syncAdapter: CloudSyncAdapter
) {

    private val routes = mutableMapOf<RouteType, AgentRoute>()

    init {
        registerRoute(AnisaManagerRoute(memoryStore))
        registerRoute(FileManagerRoute(fileManager))
        registerRoute(MemorySyncRoute(memoryStore, syncAdapter))
        registerRoute(WebIntelRoute())
        registerRoute(SummarizerRoute(memoryStore))
        registerRoute(LifestyleRoute())
        registerRoute(DesignArtRoute())
        registerRoute(LaptopBridgeRoute())
        registerRoute(MarketPulseRoute())
    }

    fun registerRoute(route: AgentRoute) {
        routes[route.routeType] = route
    }

    fun getRouteStatuses(): List<RouteStatus> {
        return RouteType.entries.map { type ->
            RouteStatus(
                type = type,
                isActive = routes.containsKey(type),
                latencyMs = 0L
            )
        }
    }

    suspend fun dispatch(prompt: String, explicitRoute: RouteType? = null): RouteResponse {
        val targetRouteType = explicitRoute ?: detectRoute(prompt)
        val route = routes[targetRouteType] ?: routes[RouteType.ANISA_MANAGER]!!
        return route.execute(RouteRequest(prompt = prompt))
    }

    suspend fun executeDirect(routeType: RouteType, request: RouteRequest): RouteResponse {
        val route = routes[routeType] ?: routes[RouteType.ANISA_MANAGER]!!
        return route.execute(request)
    }

    fun detectRoute(prompt: String): RouteType {
        val lower = prompt.lowercase().trim()
        return when {
            lower.contains("berkas") || lower.contains("file") || lower.contains("folder") ||
                lower.contains("hapus") || lower.contains("rapikan") || lower.contains("pindah") ->
                RouteType.FILE_MANAGER

            lower.contains("koding") || lower.contains("compile") || lower.contains("tugas berat") ||
                lower.contains("server laptop") || lower.contains("remote") ->
                RouteType.LAPTOP_BRIDGE

            lower.contains("sync") || lower.contains("sinkron") || lower.contains("ingatan") ||
                (lower.contains("laptop") && (lower.contains("memori") || lower.contains("data") || lower.contains("brankas"))) ->
                RouteType.MEMORY_SYNC

            lower.contains("desain") || lower.contains("furnitur") || lower.contains("ruang") ||
                lower.contains("warna") || lower.contains("estetik") ->
                RouteType.DESIGN_ART

            lower.contains("catat") || lower.contains("ide") || lower.contains("rangkum") ||
                lower.contains("memo") || lower.contains("ringkas") ->
                RouteType.SUMMARIZER

            lower.contains("cari") || lower.contains("berita") || lower.contains("info terbaru") || lower.contains("web") ->
                RouteType.WEB_INTEL

            lower.contains("cuaca") || lower.contains("sehat") || lower.contains("jadwal") || lower.contains("rutinitas") ->
                RouteType.LIFESTYLE

            lower.contains("saham") || lower.contains("harga") || lower.contains("pasar") || lower.contains("investasi") ->
                RouteType.MARKET_PULSE

            else -> RouteType.ANISA_MANAGER
        }
    }
}
