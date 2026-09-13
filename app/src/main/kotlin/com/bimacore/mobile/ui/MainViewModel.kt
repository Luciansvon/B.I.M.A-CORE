package com.bimacore.mobile.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.model.ChatMessage
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteStatus
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.model.SenderType
import com.bimacore.mobile.router.NineRouterEngine
import com.bimacore.mobile.router.RouteRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.util.UUID

class MainViewModel(
    appFilesDir: File = File(System.getProperty("java.io.tmpdir"), "bima_core_mobile")
) : ViewModel() {

    private val memoryStore = MemoryStore(appFilesDir)
    private val fileManager = FileManager()
    private val syncAdapter = CloudSyncAdapter(memoryStore)
    val routerEngine = NineRouterEngine(memoryStore, fileManager, syncAdapter)

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _routeStatuses = MutableStateFlow<List<RouteStatus>>(emptyList())
    val routeStatuses: StateFlow<List<RouteStatus>> = _routeStatuses.asStateFlow()

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    private val _isAgentThinking = MutableStateFlow(false)
    val isAgentThinking: StateFlow<Boolean> = _isAgentThinking.asStateFlow()

    init {
        _routeStatuses.value = routerEngine.getRouteStatuses()
        // Sapaan awal dari Anisa
        addAnisaMessage("Halo Bima! ✨ Senang bisa menemani hari ini. Server 9-Router di HP sudah aktif siaga, dan ingatan kita tersambung aman ke laptop. Ada yang mau kita kerjakan?")
    }

    fun getApiKey(provider: String = "9router"): String {
        return memoryStore.getFact("api_key_$provider") ?: ""
    }

    fun getServerUrl(): String {
        return memoryStore.getFact("server_9router_url") ?: com.bimacore.mobile.router.routes.AnisaManagerRoute.DEFAULT_TUNNEL_URL
    }

    fun saveServerConfig(url: String, key: String) {
        val trimmedUrl = url.trim()
        val trimmedKey = key.trim()
        if (trimmedUrl.isNotBlank()) {
            memoryStore.setFact("server_9router_url", trimmedUrl)
        }
        if (trimmedKey.isNotBlank()) {
            memoryStore.setFact("api_key_9router", trimmedKey)
        }
        val masked = if (trimmedKey.length > 8) trimmedKey.take(4) + "..." + trimmedKey.takeLast(4) else "***"
        addAnisaMessage("⚙️ Setelan 9-Router tersimpan! Server: ${getServerUrl()} (Kunci: $masked). Sekarang Anisa siap melayani Bima tanpa batas jaringan. ✨")
    }

    fun initStorageContext(cache: File?, extCache: File?) {
        fileManager.cacheDir = cache
        fileManager.externalCacheDir = extCache
    }

    fun saveApiKey(provider: String, key: String) {
        val trimmed = key.trim()
        if (trimmed.isNotBlank()) {
            memoryStore.setFact("api_key_$provider", trimmed)
            val masked = if (trimmed.length > 8) trimmed.take(4) + "..." + trimmed.takeLast(4) else "***"
            val providerLabel = when(provider) {
                "9router" -> "Server 9-Router"
                else -> provider
            }
            addAnisaMessage("🔑 Kunci $providerLabel berhasil disimpan ($masked)! Sekarang Anisa sudah tersambung ke server laptop. ✨")
        }
    }

    fun sendMessage(userText: String) {
        if (userText.isBlank()) return

        val userMessage = ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = SenderType.USER,
            text = userText
        )
        _messages.value = _messages.value + userMessage

        // Deteksi jika user paste API key langsung ke chat
        val trimmed = userText.trim()
        if (trimmed.length > 10 && (trimmed.startsWith("bma_") || trimmed.startsWith("eyJ") ||
            trimmed.length in 32..200 && !trimmed.contains(" ") && trimmed.contains("-"))) {
            // Kemungkinan besar DASHBOARD_API_TOKEN
            saveApiKey("9router", trimmed)
            return
        }

        viewModelScope.launch {
            _isAgentThinking.value = true
            try {
                val response = routerEngine.dispatch(userText)
                val anisaMessage = ChatMessage(
                    id = UUID.randomUUID().toString(),
                    sender = SenderType.ANISA,
                    text = response.textResponse,
                    actionCard = response.actionCard,
                    routeSource = response.routeUsed
                )
                _messages.value = _messages.value + anisaMessage
            } finally {
                _isAgentThinking.value = false
            }
        }
    }

    fun executeRouteDirectly(routeType: RouteType, customPrompt: String) {
        viewModelScope.launch {
            _isAgentThinking.value = true
            try {
                val response = routerEngine.executeDirect(routeType, RouteRequest(prompt = customPrompt))
                val anisaMessage = ChatMessage(
                    id = UUID.randomUUID().toString(),
                    sender = SenderType.ANISA,
                    text = response.textResponse,
                    actionCard = response.actionCard,
                    routeSource = response.routeUsed
                )
                _messages.value = _messages.value + anisaMessage
            } finally {
                _isAgentThinking.value = false
            }
        }
    }

    fun confirmActionCard(card: FileActionCard) {
        viewModelScope.launch {
            val confirmedCard = card.copy(isConfirmed = true)
            val response = routerEngine.executeDirect(
                RouteType.FILE_MANAGER,
                RouteRequest(prompt = "Konfirmasi Aksi", actionCard = confirmedCard)
            )
            val anisaMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                sender = SenderType.ANISA,
                text = response.textResponse,
                routeSource = RouteType.FILE_MANAGER
            )
            _messages.value = _messages.value + anisaMessage
        }
    }

    fun triggerSyncLaptop() {
        viewModelScope.launch {
            _isSyncing.value = true
            val response = routerEngine.executeDirect(
                RouteType.MEMORY_SYNC,
                RouteRequest(prompt = "Sync Manual")
            )
            _isSyncing.value = false
            addAnisaMessage(response.textResponse)
        }
    }

    private fun addAnisaMessage(text: String) {
        val msg = ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = SenderType.ANISA,
            text = text
        )
        _messages.value = _messages.value + msg
    }
}
