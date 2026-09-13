package com.bimacore.mobile.data

import com.bimacore.mobile.model.MemoryFact
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Penyimpan Ingatan Jangka Panjang Bima (Memory Store).
 * Menyimpan fakta tentang Bima, proyek aktif, dan preferensi kerja secara lokal
 * dengan format JSON yang ringan dan hemat baterai.
 */
class MemoryStore(private val storageDir: File) {

    private val json = Json { prettyPrint = true; ignoreUnknownKeys = true }
    private val memoryFile: File get() = File(storageDir, "bima_memory_facts.json")

    private val factsMap = mutableMapOf<String, MemoryFact>()

    init {
        loadFacts()
    }

    @Synchronized
    fun setFact(key: String, value: String): MemoryFact {
        val fact = MemoryFact(key = key, value = value, updatedAt = System.currentTimeMillis())
        factsMap[key] = fact
        persistFacts()
        return fact
    }

    @Synchronized
    fun getFact(key: String): String? = factsMap[key]?.value

    @Synchronized
    fun getAllFacts(): List<MemoryFact> = factsMap.values.toList()

    @Synchronized
    fun deleteFact(key: String): Boolean {
        val removed = factsMap.remove(key) != null
        if (removed) persistFacts()
        return removed
    }

    @Synchronized
    fun getFullContextSummary(): String {
        if (factsMap.isEmpty()) return "Belum ada fakta khusus yang tersimpan."
        return factsMap.values.joinToString("\n") { "- ${it.key}: ${it.value}" }
    }

    private fun loadFacts() {
        if (!memoryFile.exists()) {
            // Berikan fakta bawaan untuk Bima
            setFact("nama_panggilan", "Bima")
            setFact("gaya_komunikasi", "Bahasa Indonesia santai, ramah, dan ringkas")
            setFact("preferensi_desain", "Minimalis, Bento Grid, bersih, fokus obrolan")
            return
        }

        runCatching {
            val content = memoryFile.readText().removePrefix("\uFEFF")
            val list = json.decodeFromString<List<MemoryFact>>(content)
            factsMap.clear()
            list.forEach { factsMap[it.key] = it }
        }
    }

    private fun persistFacts() {
        runCatching {
            storageDir.mkdirs()
            val content = json.encodeToString(factsMap.values.toList())
            memoryFile.writeText(content)
        }
    }
}
