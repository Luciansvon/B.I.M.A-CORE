package com.bimacore.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
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
                        onSendMessage = { text -> viewModel.sendMessage(text) },
                        onConfirmAction = { card -> viewModel.confirmActionCard(card) },
                        onOpenDrawer = {
                            coroutineScope.launch { drawerState.open() }
                        }
                    )
                }
            }
        }
    }
}
