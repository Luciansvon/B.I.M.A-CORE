package com.bimacore.mobile.data

import com.bimacore.mobile.model.MemoryFact

/**
 * Boundary untuk sinkronisasi memori ke laptop.
 * v1.0.2 tidak mengklaim sinkron berhasil sebelum transport remote benar-benar dikonfigurasi.
 */
class CloudSyncAdapter(private val memoryStore: MemoryStore) {

    data class SyncResult(
        val isSuccess: Boolean,
        val syncedFactsCount: Int,
        val message: String,
        val timestamp: Long = System.currentTimeMillis()
    )

    suspend fun syncWithLaptopVault(): SyncResult {
        return SyncResult(
            isSuccess = false,
            syncedFactsCount = 0,
            message = "Sync laptop belum dikonfigurasi pada build ini. Tidak ada data yang dikirim."
        )
    }

    fun getSyncPayload(): List<MemoryFact> = memoryStore.getAllFacts()
}
