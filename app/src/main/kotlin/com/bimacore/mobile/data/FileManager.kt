package com.bimacore.mobile.data

import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.FileItem
import java.io.File

data class StorageScanResult(
    val targetFolder: String,
    val scannedPath: String,
    val totalSizeBytes: Long,
    val fileCount: Int,
    val sampleFiles: List<String>,
    val note: String
)

/**
 * Pengelola Berkas Android yang aman dan ramah pengguna.
 * Bekerja sama dengan UserSafetyGate untuk operasi berkas.
 */
class FileManager(
    private val safetyGate: UserSafetyGate = UserSafetyGate(),
    var cacheDir: File? = null,
    var externalCacheDir: File? = null
) {

    fun scanStorageDetails(targetFolder: String = "cache"): StorageScanResult {
        return when (targetFolder.lowercase()) {
            "cache" -> {
                val path = cacheDir?.absolutePath ?: "Internal Cache"
                var totalBytes = 0L
                val fileNames = mutableListOf<String>()
                var count = 0

                val collectFiles: (File?) -> Unit = { dir ->
                    dir?.listFiles()?.forEach { file ->
                        count++
                        if (fileNames.size < 5) fileNames.add(file.name)
                        totalBytes += if (file.isDirectory) getFolderSize(file) else file.length()
                    }
                }

                collectFiles(cacheDir)
                collectFiles(externalCacheDir)

                StorageScanResult(
                    targetFolder = "cache",
                    scannedPath = path,
                    totalSizeBytes = totalBytes,
                    fileCount = count,
                    sampleFiles = fileNames,
                    note = "Aplikasi berjalan dalam sandbox Android. Berkas cache aplikasi BIMA CORE dapat dipindai dan dibersihkan secara langsung. Akses ke cache aplikasi lain dilindungi oleh sistem keamanan Android."
                )
            }
            "downloads" -> {
                val downloadDir = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
                if (downloadDir != null && downloadDir.exists() && downloadDir.canRead()) {
                    val files = downloadDir.listFiles() ?: emptyArray()
                    val names = files.take(5).map { it.name }
                    StorageScanResult(
                        targetFolder = "downloads",
                        scannedPath = downloadDir.absolutePath,
                        totalSizeBytes = getFolderSize(downloadDir),
                        fileCount = files.size,
                        sampleFiles = names,
                        note = "Folder Download umum berhasil diperiksa."
                    )
                } else {
                    StorageScanResult(
                        targetFolder = "downloads",
                        scannedPath = downloadDir?.absolutePath ?: "/sdcard/Download",
                        totalSizeBytes = 0L,
                        fileCount = 0,
                        sampleFiles = emptyList(),
                        note = "Folder Download umum memerlukan izin akses penyimpanan perangkat (MANAGE_EXTERNAL_STORAGE) untuk membaca seluruh berkas bersama."
                    )
                }
            }
            else -> scanStorageDetails("cache")
        }
    }

    fun getFolderSize(dir: File?): Long {
        if (dir == null || !dir.exists()) return 0L
        if (!dir.isDirectory) return dir.length()
        var size = 0L
        dir.listFiles()?.forEach { file ->
            size += if (file.isDirectory) getFolderSize(file) else file.length()
        }
        return size
    }

    fun getAppCacheSize(): Long {
        var total = 0L
        cacheDir?.let { total += getFolderSize(it) }
        externalCacheDir?.let { total += getFolderSize(it) }
        return total
    }

    fun clearAppCache(): Pair<Boolean, Long> {
        val beforeSize = getAppCacheSize()
        var freed = 0L
        cacheDir?.listFiles()?.forEach {
            freed += getFolderSize(it)
            it.deleteRecursively()
        }
        externalCacheDir?.listFiles()?.forEach {
            freed += getFolderSize(it)
            it.deleteRecursively()
        }
        return Pair(true, if (freed > 0) freed else beforeSize)
    }

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
