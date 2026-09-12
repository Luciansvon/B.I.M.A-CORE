package com.bimacore.mobile.router

import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteType

data class RouteRequest(
    val prompt: String,
    val targetPath: String? = null,
    val actionCard: FileActionCard? = null
)

data class RouteResponse(
    val textResponse: String,
    val routeUsed: RouteType,
    val actionCard: FileActionCard? = null,
    val isSuccess: Boolean = true
)

interface AgentRoute {
    val routeType: RouteType
    suspend fun execute(request: RouteRequest): RouteResponse
}
