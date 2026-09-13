package com.bimacore.mobile

import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.UserSafetyGate
import com.bimacore.mobile.model.FileActionCard
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class SafetyGateAndFileManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var safetyGate: UserSafetyGate
    private lateinit var fileManager: FileManager
    private lateinit var testFile: File

    @Before
    fun setUp() {
        safetyGate = UserSafetyGate()
        fileManager = FileManager(safetyGate)
        testFile = tempFolder.newFile("sample_test_doc.txt")
        testFile.writeText("Isi dokumen penting Bima")
    }

    @Test
    fun testSafetyGateBlocksUnconfirmedDeletion() {
        val unconfirmedCard = FileActionCard(
            title = "Hapus Dokumen",
            description = "Menghapus dokumen pengujian",
            filePath = testFile.absolutePath,
            actionType = "DELETE",
            isConfirmed = false
        )

        val evalResult = safetyGate.evaluate(unconfirmedCard)
        assertTrue(evalResult is UserSafetyGate.SafetyCheckResult.RequiresConfirmation)

        // Verifikasi bahwa FileManager menolak penghapusan jika belum dikonfirmasi
        val deleteResult = fileManager.deleteFileSafely(unconfirmedCard)
        assertTrue("Penghapusan tanpa konfirmasi harus gagal", deleteResult.isFailure)
        assertTrue("Berkas fisik harus tetap ada", testFile.exists())
    }

    @Test
    fun testSafetyGateAllowsConfirmedDeletion() {
        val confirmedCard = FileActionCard(
            title = "Hapus Dokumen",
            description = "Menghapus dokumen pengujian",
            filePath = testFile.absolutePath,
            actionType = "DELETE",
            isConfirmed = true
        )

        val evalResult = safetyGate.evaluate(confirmedCard)
        assertTrue(evalResult is UserSafetyGate.SafetyCheckResult.SafeToExecute)

        val deleteResult = fileManager.deleteFileSafely(confirmedCard)
        assertTrue("Penghapusan dengan konfirmasi harus sukses", deleteResult.isSuccess)
        assertFalse("Berkas fisik harus sudah terhapus", testFile.exists())
    }

    @Test
    fun testFileCopyAndMoveOperations() {
        val copyDest = File(tempFolder.root, "copied_doc.txt")
        val copyResult = fileManager.copyFile(testFile.absolutePath, copyDest.absolutePath)
        assertTrue("Salin berkas harus sukses", copyResult.isSuccess)
        assertTrue(copyDest.exists())
        assertEquals("Isi dokumen penting Bima", copyDest.readText())

        val moveDest = File(tempFolder.root, "moved_doc.txt")
        val moveResult = fileManager.moveFile(copyDest.absolutePath, moveDest.absolutePath)
        assertTrue("Pindah berkas harus sukses", moveResult.isSuccess)
        assertTrue(moveDest.exists())
        assertFalse("Berkas asal harus sudah berpindah", copyDest.exists())
    }

    @Test
    fun testScanStorageDetailsAndCacheClearing() {
        val dummyCache = tempFolder.newFolder("app_cache")
        val dummyFile = File(dummyCache, "dummy_temp.log")
        dummyFile.writeText("sample temporary data")

        fileManager.cacheDir = dummyCache
        val scanResult = fileManager.scanStorageDetails("cache")
        assertEquals("cache", scanResult.targetFolder)
        assertEquals(1, scanResult.fileCount)
        assertTrue(scanResult.totalSizeBytes > 0L)
        assertTrue(scanResult.sampleFiles.contains("dummy_temp.log"))

        // Bersihkan cache fisik
        val (success, freed) = fileManager.clearAppCache()
        assertTrue(success)
        assertTrue(freed > 0L)
        assertEquals(0L, fileManager.getAppCacheSize())
    }
}
