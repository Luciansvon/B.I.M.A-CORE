package com.bimacore.mobile.router

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.RouteStatus
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.routes.*

/**
 * Server Mini Lokal: NineRouterEngine.
 * Berjalan langsung di dalam HP Bima sebagai pengatur rute cerdas (Router)
 * yang mendistribusikan setiap permintaan pengguna ke salah satu dari 9 Jalur Kemampuan.
 */
class NineRouterEngine(
    private val memoryStore: MemoryStore,
    private val fileManager: FileManager,
    private val syncAdapter: CloudSyncAdapter
) {

    private val routes = mutableMapOf<RouteType, AgentRoute>()

    init {
        val anisaManager = AnisaManagerRoute(memoryStore, fileManager, syncAdapter)
        registerRoute(anisaManager)
        registerRoute(FileManagerRoute(fileManager))
        registerRoute(MemorySyncRoute(memoryStore, syncAdapter))
        registerRoute(WebIntelRoute(memoryStore, anisaManager))
        registerRoute(SummarizerRoute(memoryStore))
        registerRoute(LifestyleRoute(anisaManager))
        registerRoute(DesignArtRoute(anisaManager))
        registerRoute(LaptopBridgeRoute(anisaManager))
        registerRoute(MarketPulseRoute(anisaManager))
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
        // Semua pesan alami masuk ke AnisaManagerRoute (Agent Harness) yang otonom memicu tool
        val targetRouteType = explicitRoute ?: RouteType.ANISA_MANAGER
        val route = routes[targetRouteType] ?: routes[RouteType.ANISA_MANAGER]!!
        val request = RouteRequest(prompt = prompt)
        return route.execute(request)
    }

    suspend fun executeDirect(routeType: RouteType, request: RouteRequest): RouteResponse {
        val route = routes[routeType] ?: routes[RouteType.ANISA_MANAGER]!!
        return route.execute(request)
    }

    fun detectRoute(prompt: String): RouteType {
        // Otak Anisa yang menentukan tool yang relevan via OpenAI Tool Calling
        return RouteType.ANISA_MANAGER
    }
}
