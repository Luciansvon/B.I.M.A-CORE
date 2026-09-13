package com.bimacore.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.bimacore.mobile.model.RouteType
import com.bimacore.mobile.ui.ChatScreen
import com.bimacore.mobile.ui.MainViewModel
import com.bimacore.mobile.ui.SidebarDrawerContent
import com.bimacore.mobile.ui.theme.BimaCoreMobileTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            BimaCoreMobileTheme {
                val viewModel: MainViewModel = viewModel()
                val messages by viewModel.messages.collectAsState()
                val routeStatuses by viewModel.routeStatuses.collectAsState()
                val isAgentThinking by viewModel.isAgentThinking.collectAsState()

                val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
                val coroutineScope = rememberCoroutineScope()

                var showApiKeyDialog by remember { mutableStateOf(false) }
                var routerKeyInput by remember { mutableStateOf(viewModel.getApiKey("9router")) }

                ModalNavigationDrawer(
                    drawerState = drawerState,
                    drawerContent = {
                        SidebarDrawerContent(
                            routeStatuses = routeStatuses,
                            onSelectAction = { action ->
                                when (action) {
                                    "FOLDER" -> viewModel.executeRouteDirectly(
                                        RouteType.FILE_MANAGER,
                                        "Tolong periksa folder berkas di HP"
                                    )
                                    "SYNC" -> viewModel.triggerSyncLaptop()
                                    "MEMO" -> viewModel.executeRouteDirectly(
                                        RouteType.SUMMARIZER,
                                        "Tampilkan ringkasan catatan ingatan terakhir"
                                    )
                                    "NEW_CHAT" -> viewModel.sendMessage("Halo Anisa, kita mulai sesi obrolan baru ya!")
                                    "API_KEY" -> {
                                        routerKeyInput = viewModel.getApiKey("9router")
                                        showApiKeyDialog = true
                                    }
                                }
                            },
                            onCloseDrawer = {
                                coroutineScope.launch { drawerState.close() }
                            }
                        )
                    }
                ) {
                    ChatScreen(
                        messages = messages,
                        isAgentThinking = isAgentThinking,
                        onSendMessage = { text -> viewModel.sendMessage(text) },
                        onConfirmAction = { card -> viewModel.confirmActionCard(card) },
                        onOpenDrawer = {
                            coroutineScope.launch { drawerState.open() }
                        }
                    )

                    if (showApiKeyDialog) {
                        AlertDialog(
                            onDismissRequest = { showApiKeyDialog = false },
                            title = { Text("Kunci Server 9-Router") },
                            text = {
                                Column(
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text(
                                        "Masukkan DASHBOARD_API_TOKEN dari file .env di laptop " +
                                        "agar Anisa bisa terhubung ke server BIMA CORE:"
                                    )
                                    OutlinedTextField(
                                        value = routerKeyInput,
                                        onValueChange = { routerKeyInput = it },
                                        label = { Text("Kunci Server 9-Router") },
                                        placeholder = { Text("Tempel token dari .env laptop...") },
                                        singleLine = false,
                                        maxLines = 3,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            },
                            confirmButton = {
                                Button(
                                    onClick = {
                                        if (routerKeyInput.isNotBlank()) {
                                            viewModel.saveApiKey("9router", routerKeyInput)
                                        }
                                        showApiKeyDialog = false
                                    }
                                ) {
                                    Text("Simpan & Sambungkan")
                                }
                            },
                            dismissButton = {
                                TextButton(onClick = { showApiKeyDialog = false }) {
                                    Text("Batal")
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}
