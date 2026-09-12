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
import androidx.compose.ui.text.input.PasswordVisualTransformation
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

                val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
                val coroutineScope = rememberCoroutineScope()

                var showCredentialDialog by remember { mutableStateOf(false) }
                var openRouterInput by remember { mutableStateOf("") }
                var geminiInput by remember { mutableStateOf("") }

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
                                        openRouterInput = ""
                                        geminiInput = ""
                                        showCredentialDialog = true
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
                        onSendMessage = viewModel::sendMessage,
                        onConfirmAction = viewModel::confirmActionCard,
                        onOpenDrawer = {
                            coroutineScope.launch { drawerState.open() }
                        }
                    )

                    if (showCredentialDialog) {
                        AlertDialog(
                            onDismissRequest = { showCredentialDialog = false },
                            title = { Text("Pengaturan Provider AI") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("Kredensial disimpan terenkripsi oleh Android Keystore.")
                                    Text(
                                        "OpenRouter: ${viewModel.getCredentialMasked("openrouter").ifBlank { "belum disimpan" }}"
                                    )
                                    OutlinedTextField(
                                        value = openRouterInput,
                                        onValueChange = { openRouterInput = it },
                                        label = { Text("Kredensial OpenRouter baru") },
                                        placeholder = { Text("Kosongkan jika tidak ingin mengganti") },
                                        visualTransformation = PasswordVisualTransformation(),
                                        singleLine = true,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                    Text(
                                        "Gemini: ${viewModel.getCredentialMasked("gemini").ifBlank { "belum disimpan" }}"
                                    )
                                    OutlinedTextField(
                                        value = geminiInput,
                                        onValueChange = { geminiInput = it },
                                        label = { Text("Kredensial Gemini baru") },
                                        placeholder = { Text("Kosongkan jika tidak ingin mengganti") },
                                        visualTransformation = PasswordVisualTransformation(),
                                        singleLine = true,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            },
                            confirmButton = {
                                Button(
                                    onClick = {
                                        if (openRouterInput.isNotBlank()) {
                                            viewModel.saveCredential("openrouter", openRouterInput)
                                        }
                                        if (geminiInput.isNotBlank()) {
                                            viewModel.saveCredential("gemini", geminiInput)
                                        }
                                        openRouterInput = ""
                                        geminiInput = ""
                                        showCredentialDialog = false
                                    }
                                ) {
                                    Text("Simpan")
                                }
                            },
                            dismissButton = {
                                TextButton(
                                    onClick = {
                                        openRouterInput = ""
                                        geminiInput = ""
                                        showCredentialDialog = false
                                    }
                                ) {
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
