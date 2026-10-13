package com.blueradar.app.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val NeonCyan = Color(0xFF00F5FF)
val NeonMagenta = Color(0xFFFF00E5)
val NeonGreen = Color(0xFF39FF14)
val NeonOrange = Color(0xFFFF6B00)
val DeepSpace = Color(0xFF050510)
val DarkPanel = Color(0xFF0D0D1A)
val GridLine = Color(0xFF1A1A3A)
val WarningRed = Color(0xFFFF2D55)
val SoftWhite = Color(0xFFE8F0FF)

private val DarkColorScheme = darkColorScheme(
    primary = NeonCyan,
    onPrimary = DeepSpace,
    secondary = NeonMagenta,
    onSecondary = DeepSpace,
    tertiary = NeonGreen,
    background = DeepSpace,
    surface = DarkPanel,
    onBackground = SoftWhite,
    onSurface = SoftWhite,
    error = WarningRed,
    surfaceVariant = Color(0xFF151528),
    onSurfaceVariant = Color(0xFFA0B0D0)
)

@Composable
fun BlueRadarTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography(),
        content = content
    )
}
