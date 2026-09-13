package com.bimacore.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bimacore.mobile.model.RouteStatus
import com.bimacore.mobile.ui.theme.*

@Composable
fun SidebarDrawerContent(
    routeStatuses: List<RouteStatus>,
    onSelectAction: (String) -> Unit,
    onCloseDrawer: () -> Unit
) {
    ModalDrawerSheet(
        drawerContainerColor = DarkSlateSurface,
        drawerContentColor = PureWhiteText,
        modifier = Modifier.width(320.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxHeight()
                .padding(20.dp)
        ) {
            // Profil Anisa Core
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 24.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(WarmAmberAccent),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "AC",
                        color = Color.Black,
                        fontSize = 18.sp
                    )
                }
                Spacer(modifier = Modifier.width(14.dp))
                Column {
                    Text(
                        text = "Anisa Core",
                        fontSize = 18.sp,
                        color = PureWhiteText
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(GlowingGreen)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Aktif di HP",
                            fontSize = 12.sp,
                            color = SoftGrayText
                        )
                    }
                }
            }

            // Kartu 9-Router Server dengan 9 Titik Cahaya
            Surface(
                color = DarkSlateCard,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 20.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "9-Router Server",
                            fontSize = 15.sp,
                            color = WarmAmberLight
                        )
                        Icon(
                            imageVector = Icons.Default.Dns,
                            contentDescription = "Server",
                            tint = WarmAmberAccent,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    // 9 Titik Indikator Rute
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        routeStatuses.take(9).forEach { status ->
                            Box(
                                modifier = Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(if (status.isActive) WarmAmberAccent else SoftGrayText)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = "Server Lokal HP Siaga (9 Jalur)",
                        fontSize = 11.sp,
                        color = SoftGrayText
                    )
                }
            }

            Text(
                text = "MENU UTAMA",
                fontSize = 11.sp,
                color = SoftGrayText,
                modifier = Modifier.padding(bottom = 8.dp)
            )

            // Item Menu Bilah Samping
            SidebarMenuItem(
                icon = Icons.Default.Folder,
                label = "Kelola Berkas HP",
                subtitle = "Bereskan & pindahkan dokumen",
                onClick = {
                    onSelectAction("FOLDER")
                    onCloseDrawer()
                }
            )

            SidebarMenuItem(
                icon = Icons.Default.Sync,
                label = "Sync Laptop",
                subtitle = "Tersambung ke brankas online",
                onClick = {
                    onSelectAction("SYNC")
                    onCloseDrawer()
                }
            )

            SidebarMenuItem(
                icon = Icons.Default.Key,
                label = "Kunci API",
                subtitle = "Kunci server 9-Router laptop",
                onClick = {
                    onSelectAction("API_KEY")
                    onCloseDrawer()
                }
            )

            SidebarMenuItem(
                icon = Icons.Default.NoteAlt,
                label = "Catatan & Memori",
                subtitle = "Lihat fakta & ide tersimpan",
                onClick = {
                    onSelectAction("MEMO")
                    onCloseDrawer()
                }
            )

            SidebarMenuItem(
                icon = Icons.Default.ChatBubbleOutline,
                label = "Obrolan Baru",
                subtitle = "Mulai sesi percakapan segar",
                onClick = {
                    onSelectAction("NEW_CHAT")
                    onCloseDrawer()
                }
            )

            Spacer(modifier = Modifier.weight(1f))

            Text(
                text = "B.I.M.A Core Mobile v1.0.2\nStandar B.I.M.A-DEV-INFRA",
                fontSize = 11.sp,
                color = SoftGrayText,
                lineHeight = 16.sp
            )
        }
    }
}

@Composable
fun SidebarMenuItem(
    icon: ImageVector,
    label: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Surface(
        color = Color.Transparent,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 4.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = WarmAmberAccent,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(14.dp))
            Column {
                Text(
                    text = label,
                    fontSize = 14.sp,
                    color = PureWhiteText
                )
                Text(
                    text = subtitle,
                    fontSize = 11.sp,
                    color = SoftGrayText
                )
            }
        }
    }
}
