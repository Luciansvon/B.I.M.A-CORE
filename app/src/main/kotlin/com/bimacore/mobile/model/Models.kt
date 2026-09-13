package com.bimacore.mobile.model

import kotlinx.serialization.Serializable

@Serializable
enum class RouteType(val label: String, val description: String) {
    ANISA_MANAGER("Anisa Manager", "Pusat komando dan teman bicara"),
    FILE_MANAGER("Kelola Berkas", "Operasi berkas aman di HP"),
    MEMORY_SYNC("Sync Memori", "Sinkronisasi ingatan ke laptop"),
    WEB_INTEL("Intel & Berita", "Pencarian fakta dan info online"),
    SUMMARIZER("Perangkum", "Catatan dan ringkasan kilat"),
    LIFESTYLE("Gaya Hidup", "Pengingat rutinitas & cuaca"),
    DESIGN_ART("Inspirasi Desain", "Kreativitas & ide visual"),
    LAPTOP_BRIDGE("Jembatan Laptop", "Delegasi tugas komputasi berat"),
    MARKET_PULSE("Pantauan Pasar", "Ringkasan tren bisnis & saham")
}

@Serializable
enum class SenderType {
    USER,
    ANISA
}

@Serializable
data class FileActionCard(
    val title: String,
    val description: String,
    val filePath: String,
    val actionType: String, // "CLEAN", "MOVE", "DELETE", "COPY"
    val isConfirmed: Boolean = false,
    val isRequiresSafetyGate: Boolean = true
)

@Serializable
data class ChatMessage(
    val id: String,
    val sender: SenderType,
    val text: String,
    val timestamp: Long = System.currentTimeMillis(),
    val actionCard: FileActionCard? = null,
    val routeSource: RouteType? = null
)

@Serializable
data class FileItem(
    val name: String,
    val path: String,
    val sizeBytes: Long,
    val isDirectory: Boolean,
    val lastModified: Long
)

@Serializable
data class MemoryFact(
    val key: String,
    val value: String,
    val updatedAt: Long = System.currentTimeMillis()
)

@Serializable
data class RouteStatus(
    val type: RouteType,
    val isActive: Boolean = true,
    val latencyMs: Long = 12
)
