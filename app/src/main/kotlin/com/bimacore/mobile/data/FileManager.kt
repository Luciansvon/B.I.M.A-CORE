package com.bimacore.mobile.data

import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.FileItem
import java.io.File

/**
 * Pengelola Berkas Android yang aman dan ramah pengguna.
 * Bekerja sama dengan UserSafetyGate untuk operasi berkas.
 */
class FileManager(private val safetyGate: UserSafetyGate = UserSafetyGate()) {

    fun listDirectory(dirPath: String): List<FileItem> {
        val dir = File(dirPath)
        if (!dir.exists() || !dir.isDirectory) {
            return emptyList()
        }

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

    fun readFileContent(filePath: String, maxChars: Int = 10000): Result<String> {
        return runCatching {
            val file = File(filePath)
            if (!file.exists()) error("Berkas tidak ditemukan: $filePath")
            if (file.isDirectory) error("Jalur adalah folder, bukan berkas")
            file.readText().take(maxChars)
        }
    }

    fun writeFileContent(filePath: String, content: String): Result<Unit> {
        return runCatching {
            val file = File(filePath)
            file.parentFile?.mkdirs()
            file.writeText(content)
        }
    }

    fun copyFile(sourcePath: String, destPath: String): Result<Unit> {
        return runCatching {
            val src = File(sourcePath)
            val dst = File(destPath)
            if (!src.exists()) error("Berkas sumber tidak ditemukan: $sourcePath")
            dst.parentFile?.mkdirs()
            src.copyTo(dst, overwrite = true)
        }
    }

    fun moveFile(sourcePath: String, destPath: String): Result<Unit> {
        return runCatching {
            val src = File(sourcePath)
            val dst = File(destPath)
            if (!src.exists()) error("Berkas sumber tidak ditemukan: $sourcePath")
            dst.parentFile?.mkdirs()
            if (!src.renameTo(dst)) {
                src.copyTo(dst, overwrite = true)
                src.delete()
            }
        }
    }

    fun deleteFileSafely(actionCard: FileActionCard): Result<String> {
        return runCatching {
            val gateResult = safetyGate.evaluate(actionCard)
            when (gateResult) {
                is UserSafetyGate.SafetyCheckResult.RequiresConfirmation -> {
                    error(gateResult.warningMessage)
                }
                is UserSafetyGate.SafetyCheckResult.Blocked -> {
                    error("Operasi dibatalkan: ${gateResult.reason}")
                }
                is UserSafetyGate.SafetyCheckResult.SafeToExecute -> {
                    val file = File(actionCard.filePath)
                    if (!file.exists()) {
                        "Berkas '${file.name}' sudah tidak ada."
                    } else if (file.isDirectory) {
                        file.deleteRecursively()
                        "Folder '${file.name}' berhasil dibersihkan dengan aman."
                    } else {
                        file.delete()
                        "Berkas '${file.name}' berhasil dihapus dengan aman."
                    }
                }
            }
        }
    }
}
