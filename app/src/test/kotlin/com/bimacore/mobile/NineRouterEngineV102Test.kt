package com.bimacore.mobile

import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.router.NineRouterEngine
import com.bimacore.mobile.router.RouteRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class NineRouterEngineV102Test {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var memoryStore: MemoryStore
    private lateinit var routerEngine: NineRouterEngine

    @Before
    fun setUp() {
        memoryStore = MemoryStore(tempFolder.newFolder("bima_test_store"))
        val fileManager = FileManager()
        routerEngine = NineRouterEngine(memoryStore, fileManager, CloudSyncAdapter(memoryStore))
    }

    @Test
    fun allNineRoutesAreRegisteredWithoutFakeLatency() {
        val statuses = routerEngine.getRouteStatuses()
        assertEquals(9, statuses.size)
        assertTrue(statuses.all { it.isActive })
        assertTrue(statuses.all { it.latencyMs == 0L })
    }

    @Test
    fun routeIntentDetectionWorks() {
        assertEquals(RouteType.FILE_MANAGER, routerEngine.detectRoute("tolong bersihkan berkas unduhan"))
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
    fun fileCleanupStillRequiresConfirmation() = runBlocking {
        val response = routerEngine.dispatch("tolong rapikan berkas di folder Download")
        assertEquals(RouteType.FILE_MANAGER, response.routeUsed)
        assertNotNull(response.actionCard)
        assertEquals("CLEAN", response.actionCard?.actionType)
        assertFalse(response.actionCard!!.isConfirmed)
    }

    @Test
    fun memorySyncDoesNotFakeRemoteSuccess() = runBlocking {
        memoryStore.setFact("proyek_aktif", "Kursi Japandi")
        val response = routerEngine.executeDirect(RouteType.MEMORY_SYNC, RouteRequest(prompt = "Sync"))
        assertEquals(RouteType.MEMORY_SYNC, response.routeUsed)
        assertFalse(response.isSuccess)
        assertTrue(response.textResponse.contains("belum dikonfigurasi", ignoreCase = true))
        assertTrue(response.textResponse.contains("Kursi Japandi"))
    }

    @Test
    fun offlineWebRouteDoesNotFakeSearch() = runBlocking {
        val response = routerEngine.dispatch("cari berita terbaru")
        assertEquals(RouteType.WEB_INTEL, response.routeUsed)
        assertFalse(response.isSuccess)
        assertTrue(response.textResponse.contains("belum dijalankan", ignoreCase = true))
    }

    @Test
    fun offlineLaptopBridgeDoesNotFakeDelivery() = runBlocking {
        val response = routerEngine.dispatch("jalankan tugas berat di server laptop")
        assertEquals(RouteType.LAPTOP_BRIDGE, response.routeUsed)
        assertFalse(response.isSuccess)
        assertTrue(response.textResponse.contains("belum dikonfigurasi", ignoreCase = true))
    }
}
