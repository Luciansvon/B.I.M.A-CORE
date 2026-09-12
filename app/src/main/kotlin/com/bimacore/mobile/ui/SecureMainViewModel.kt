package com.bimacore.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bimacore.mobile.data.AiProviderClient
import com.bimacore.mobile.data.CloudSyncAdapter
import com.bimacore.mobile.data.FileManager
import com.bimacore.mobile.data.MemoryStore
import com.bimacore.mobile.data.SecureApiKeyStore
import com.bimacore.mobile.model.ChatMessage
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.RouteStatus
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.model.SenderType
import com.bimacore.mobile.router.NineRouterEngine
import com.bimacore.mobile.router.RouteRequest
import com.bimacore.mobile.router.RouteResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val memoryStore = MemoryStore(application.filesDir)
    private val fileManager = FileManager()
    private val syncAdapter = CloudSyncAdapter(memoryStore)
    private val secretStore = SecureApiKeyStore(application)
    private val aiProviderClient = AiProviderClient(secretStore)

    val routerEngine = NineRouterEngine(memoryStore, fileManager, syncAdapter)

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _routeStatuses = MutableStateFlow<List<RouteStatus>>(emptyList())
    val routeStatuses: StateFlow<List<RouteStatus>> = _routeStatuses.asStateFlow()

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    init {
        _routeStatuses.value = routerEngine.getRouteStatuses()
        addAnisaMessage("Halo Mas Bima! ✨ 9-Router lokal siap. AI online aktif saat kredensial provider sudah tersimpan aman.")
    }

    fun getCredentialMasked(provider: String): String {
        val secret = secretStore.get(provider) ?: return ""
        return maskSecret(secret)
    }

    fun saveCredential(provider: String, secret: String): Boolean {
        val normalizedProvider = provider.trim().lowercase()
        val trimmed = secret.trim()
        if (normalizedProvider !in SUPPORTED_PROVIDERS || trimmed.length < MIN_SECRET_LENGTH) {
            addAnisaMessage("⚠️ Kredensial $normalizedProvider tidak valid dan tidak disimpan.")
            return false
        }

        secretStore.put(normalizedProvider, trimmed)
        addAnisaMessage("🔐 Kredensial $normalizedProvider tersimpan terenkripsi (${maskSecret(trimmed)}).")
        return true
    }

    fun sendMessage(userText: String) {
        if (userText.isBlank()) return

        val userMessage = ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = SenderType.USER,
            text = userText
        )
        _messages.value = _messages.value + userMessage

        viewModelScope.launch {
            val routeType = routerEngine.detectRoute(userText)
            val response = if (routeType in ONLINE_AI_ROUTES && aiProviderClient.hasAnyKey()) {
                aiProviderClient.generate(routeType, userText).fold(
                    onSuccess = { text -> RouteResponse(textResponse = text, routeUsed = routeType) },
                    onFailure = { error ->
                        val local = routerEngine.dispatch(userText, routeType)
                        local.copy(
                            textResponse = "⚠️ AI online gagal: ${error.message ?: "error tidak diketahui"}\n\n${local.textResponse}"
                        )
                    }
                )
            } else {
                routerEngine.dispatch(userText, routeType)
            }

            _messages.value = _messages.value + ChatMessage(
                id = UUID.randomUUID().toString(),
                sender = SenderType.ANISA,
                text = response.textResponse,
                actionCard = response.actionCard,
                routeSource = response.routeUsed
            )
        }
    }

    fun executeRouteDirectly(routeType: RouteType, customPrompt: String) {
        viewModelScope.launch {
            val response = routerEngine.executeDirect(routeType, RouteRequest(prompt = customPrompt))
            _messages.value = _messages.value + ChatMessage(
                id = UUID.randomUUID().toString(),
                sender = SenderType.ANISA,
                text = response.textResponse,
                actionCard = response.actionCard,
                routeSource = response.routeUsed
            )
        }
    }

    fun confirmActionCard(card: FileActionCard) {
        viewModelScope.launch {
            val response = routerEngine.executeDirect(
                RouteType.FILE_MANAGER,
                RouteRequest(prompt = "Konfirmasi Aksi", actionCard = card.copy(isConfirmed = true))
            )
            _messages.value = _messages.value + ChatMessage(
                id = UUID.randomUUID().toString(),
                sender = SenderType.ANISA,
                text = response.textResponse,
                routeSource = RouteType.FILE_MANAGER
            )
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

    private fun maskSecret(secret: String): String = when {
        secret.length <= 8 -> "••••••••"
        else -> "${secret.take(4)}••••${secret.takeLast(4)}"
    }

    private fun addAnisaMessage(text: String) {
        _messages.value = _messages.value + ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = SenderType.ANISA,
            text = text
        )
    }

    private companion object {
        const val MIN_SECRET_LENGTH = 16
        val SUPPORTED_PROVIDERS = setOf("openrouter", "gemini")
        val ONLINE_AI_ROUTES = setOf(
            RouteType.ANISA_MANAGER,
            RouteType.WEB_INTEL,
            RouteType.LIFESTYLE,
            RouteType.DESIGN_ART,
            RouteType.MARKET_PULSE
        )
    }
}
