package com.bimacore.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bimacore.mobile.model.ChatMessage
import com.bimacore.mobile.model.FileActionCard
import com.bimacore.mobile.model.SenderType
import com.bimacore.mobile.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    messages: List<ChatMessage>,
    onSendMessage: (String) -> Unit,
    onConfirmAction: (FileActionCard) -> Unit,
    onOpenDrawer: () -> Unit
) {
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        containerColor = DarkSlateBackground,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = DarkSlateSurface,
                    titleContentColor = PureWhiteText,
                    navigationIconContentColor = PureWhiteText
                ),
                title = {
                    Column {
                        Text(
                            text = "ANISA - BIMA CORE",
                            fontSize = 16.sp
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(GlowingGreen)
                            )
                            Spacer(modifier = Modifier.width(5.dp))
                            Text(
                                text = "Bima: Online • 9-Router Siaga",
                                fontSize = 11.sp,
                                color = SoftGrayText
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onOpenDrawer) {
                        Icon(
                            imageVector = Icons.Default.Menu,
                            contentDescription = "Buka Menu",
                            tint = WarmAmberAccent
                        )
                    }
                }
            )
        },
        bottomBar = {
            Surface(
                color = DarkSlateSurface,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                        .navigationBarsPadding()
                        .imePadding(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    TextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = {
                            Text(
                                text = "Ketik pesan untuk Anisa...",
                                color = SoftGrayText,
                                fontSize = 14.sp
                            )
                        },
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = DarkSlateCard,
                            unfocusedContainerColor = DarkSlateCard,
                            focusedTextColor = PureWhiteText,
                            unfocusedTextColor = PureWhiteText,
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent
                        ),
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.weight(1f),
                        singleLine = false,
                        maxLines = 4
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = { /* Aksi mikrofon */ },
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(DarkSlateCard)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = "Suara",
                            tint = WarmAmberAccent
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                onSendMessage(inputText)
                                inputText = ""
                            }
                        },
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(WarmAmberAccent)
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Kirim",
                            tint = Color.Black
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            items(messages, key = { it.id }) { message ->
                ChatMessageItem(
                    message = message,
                    onConfirmAction = onConfirmAction
                )
            }
        }
    }
}

@Composable
fun ChatMessageItem(
    message: ChatMessage,
    onConfirmAction: (FileActionCard) -> Unit
) {
    val isUser = message.sender == SenderType.USER

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 4.dp)
        ) {
            Text(
                text = if (isUser) "Bima" else "Anisa ✨",
                fontSize = 12.sp,
                color = if (isUser) WarmAmberLight else SoftGrayText
            )
        }

        Surface(
            color = if (isUser) WarmAmberAccent else DarkSlateCard,
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp
            ),
            modifier = Modifier.widthIn(max = 300.dp)
        ) {
            Text(
                text = message.text,
                color = if (isUser) Color.Black else PureWhiteText,
                fontSize = 14.sp,
                lineHeight = 20.sp,
                modifier = Modifier.padding(14.dp)
            )
        }

        // Kartu Aksi Berkas (jika ada)
        message.actionCard?.let { card ->
            Spacer(modifier = Modifier.height(8.dp))
            Surface(
                color = DarkSlateSurface,
                shape = RoundedCornerShape(16.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, WarmAmberAccent.copy(alpha = 0.4f)),
                modifier = Modifier.widthIn(max = 300.dp)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Folder,
                            contentDescription = "Folder",
                            tint = WarmAmberAccent,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = card.title,
                            fontSize = 14.sp,
                            color = PureWhiteText
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = card.description,
                        fontSize = 12.sp,
                        color = SoftGrayText
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                    Button(
                        onClick = { onConfirmAction(card) },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = WarmAmberAccent,
                            contentColor = Color.Black
                        ),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(text = "Setujui & Jalankan Aksi", fontSize = 12.sp)
                    }
                }
            }
        }
    }
}
