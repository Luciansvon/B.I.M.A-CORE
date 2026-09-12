package com.bimacore.mobile.data

import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.FileItem
import java.io.File

/**
 * Pengelola berkas lokal dengan proteksi operasi destruktif.
 * Akses storage luas Android tidak diasumsikan; caller harus memberi path yang memang dapat diakses app.
 */
class FileManager(private val safetyGate: UserSafetyGate = UserSafetyGate()) {

    fun listDirectory(dirPath: String): List<FileItem> {
        val dir = File(dirPath)
        if (!dir.exists() || !dir.isDirectory) return emptyList()

        val children = dir.listFiles() ?: return emptyList()
        return children.map { file ->
            FileItem(
                name = file.name,
                path = file.absolutePath,
                sizeBytes = if (file.isDirectory) 0L else file.length(),
                isDirectory = file.isDirectory,
                lastModified = file.lastModified()
            )
        }.sortedWith(compareByDescending<FileItem> { it.isDirectory }.thenBy { it.name.lowercase() })
    }

    fun readFileContent(filePath: String, maxChars: Int = 10000): Result<String> = runCatching {
        val file = File(filePath)
        if (!file.exists()) error("Berkas tidak ditemukan: $filePath")
        if (file.isDirectory) error("Jalur adalah folder, bukan berkas")
        file.readText().take(maxChars)
    }

    fun writeFileContent(filePath: String, content: String): Result<Unit> = runCatching {
        val file = File(filePath)
        if (file.exists()) error("Tujuan sudah ada dan tidak boleh ditimpa otomatis: $filePath")
        file.parentFile?.mkdirs()
        file.writeText(content)
    }

    fun copyFile(sourcePath: String, destPath: String): Result<Unit> = runCatching {
        val src = File(sourcePath)
        val dst = File(destPath)
        if (!src.exists()) error("Berkas sumber tidak ditemukan: $sourcePath")
        if (dst.exists()) error("Tujuan sudah ada dan tidak boleh ditimpa otomatis: $destPath")
        dst.parentFile?.mkdirs()
        src.copyTo(dst, overwrite = false)
    }

    fun moveFile(sourcePath: String, destPath: String): Result<Unit> = runCatching {
        val src = File(sourcePath)
        val dst = File(destPath)
        if (!src.exists()) error("Berkas sumber tidak ditemukan: $sourcePath")
        if (dst.exists()) error("Tujuan sudah ada dan tidak boleh ditimpa otomatis: $destPath")
        dst.parentFile?.mkdirs()

        if (!src.renameTo(dst)) {
            src.copyTo(dst, overwrite = false)
            if (!src.delete()) {
                dst.delete()
                error("Gagal menghapus sumber setelah penyalinan; perpindahan dibatalkan")
            }
        }
    }

    fun deleteFileSafely(actionCard: FileActionCard): Result<String> = runCatching {
        when (val gateResult = safetyGate.evaluate(actionCard)) {
            is UserSafetyGate.SafetyCheckResult.RequiresConfirmation -> error(gateResult.warningMessage)
            is UserSafetyGate.SafetyCheckResult.Blocked -> error("Operasi dibatalkan: ${gateResult.reason}")
            is UserSafetyGate.SafetyCheckResult.SafeToExecute -> {
                val file = File(actionCard.filePath)
                if (!file.exists()) {
                    "Berkas '${file.name}' sudah tidak ada."
                } else {
                    val deleted = if (file.isDirectory) file.deleteRecursively() else file.delete()
                    if (!deleted) error("Gagal menghapus '${file.name}'")
                    if (file.isDirectory) {
                        "Folder '${file.name}' berhasil dibersihkan dengan aman."
                    } else {
                        "Berkas '${file.name}' berhasil dihapus dengan aman."
                    }
                }
            }
        }
    }
}
