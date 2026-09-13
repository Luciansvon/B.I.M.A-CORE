package com.bimacore.mobile

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.NineRouterEngine
import com.bimacore.mobile.router.RouteRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class NineRouterEngineTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var memoryStore: MemoryStore
    private lateinit var fileManager: FileManager
    private lateinit var syncAdapter: CloudSyncAdapter
    private lateinit var routerEngine: NineRouterEngine

    @Before
    fun setUp() {
        val rootDir = tempFolder.newFolder("bima_test_store")
        memoryStore = MemoryStore(rootDir)
        fileManager = FileManager()
        syncAdapter = CloudSyncAdapter(memoryStore)
        routerEngine = NineRouterEngine(memoryStore, fileManager, syncAdapter)
    }

    @Test
    fun testAllNineRoutesAreActive() {
        val statuses = routerEngine.getRouteStatuses()
        assertEquals("Harus ada tepat 9 jalur rute agen", 9, statuses.size)
        assertTrue("Semua 9 rute harus berstatus aktif", statuses.all { it.isActive })
    }

    @Test
    fun testRouteIntentDetection() {
        assertEquals(RouteType.FILE_MANAGER, routerEngine.detectRoute("tolong bersihkan berkas unduhan"))
        assertEquals(RouteType.FILE_MANAGER, routerEngine.detectRoute("bisa bantu aku bersihin sampah di hp ku?"))
        assertEquals(RouteType.MEMORY_SYNC, routerEngine.detectRoute("sinkronkan memori ke laptop"))
        assertEquals(RouteType.SUMMARIZER, routerEngine.detectRoute("catat ide baru untuk proyek meja"))
        assertEquals(RouteType.WEB_INTEL, routerEngine.detectRoute("cari info berita teknologi terbaru"))
        assertEquals(RouteType.LIFESTYLE, routerEngine.detectRoute("bagaimana cuaca hari ini"))
        assertEquals(RouteType.DESIGN_ART, routerEngine.detectRoute("beri ide desain ruang tamu minimalis"))
        assertEquals(RouteType.LAPTOP_BRIDGE, routerEngine.detectRoute("jalankan koding berat di server laptop"))
        assertEquals(RouteType.MARKET_PULSE, routerEngine.detectRoute("cek harga saham IDX hari ini"))
        assertEquals(RouteType.ANISA_MANAGER, routerEngine.detectRoute("halo selamat pagi"))
    }

    @Test
    fun testDispatchToAnisaManager() = runBlocking {
        val response = routerEngine.dispatch("Halo Anisa")
        assertEquals(RouteType.ANISA_MANAGER, response.routeUsed)
        assertTrue(response.textResponse.contains("Server 9-Router", ignoreCase = true))
        assertFalse("Tanpa kunci server, rute menginstruksikan pengaturan kunci", response.isSuccess)
    }

    @Test
    fun testDispatchToFileManagerWithSafetyGate() = runBlocking {
        val response = routerEngine.dispatch("tolong rapikan berkas di folder Download")
        assertEquals(RouteType.FILE_MANAGER, response.routeUsed)
        assertNotNull("Harus menghasilkan kartu konfirmasi berkas", response.actionCard)
        assertEquals("CLEAN", response.actionCard?.actionType)
        assertFalse("Kartu baru tidak boleh otomatis terkonfirmasi", response.actionCard!!.isConfirmed)
    }

    @Test
    fun testDirectExecutionOfMemorySync() = runBlocking {
        memoryStore.setFact("proyek_aktif", "Kursi Japandi")
        val response = routerEngine.executeDirect(RouteType.MEMORY_SYNC, RouteRequest(prompt = "Sync"))
        assertEquals(RouteType.MEMORY_SYNC, response.routeUsed)
        assertTrue(response.textResponse.contains("Sinkronisasi berhasil"))
        assertTrue(response.textResponse.contains("Kursi Japandi"))
    }
}
