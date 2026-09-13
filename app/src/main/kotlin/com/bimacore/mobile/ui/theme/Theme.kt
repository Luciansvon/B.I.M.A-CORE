package com.bimacore.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val DarkSlateBackground = Color(0xFF131517)
val DarkSlateSurface = Color(0xFF1C1F23)
val DarkSlateCard = Color(0xFF24292F)
val WarmAmberAccent = Color(0xFFE5A93C)
val WarmAmberLight = Color(0xFFF3C76F)
val SoftGrayText = Color(0xFF9BA3AF)
val PureWhiteText = Color(0xFFF5F7FA)
val GlowingGreen = Color(0xFF34D399)

private val DarkColorScheme = darkColorScheme(
    primary = WarmAmberAccent,
    onPrimary = Color.Black,
    secondary = WarmAmberLight,
    onSecondary = Color.Black,
    background = DarkSlateBackground,
    onBackground = PureWhiteText,
    surface = DarkSlateSurface,
    onSurface = PureWhiteText,
    surfaceVariant = DarkSlateCard,
    onSurfaceVariant = SoftGrayText
)

@Composable
fun BimaCoreMobileTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
