package com.reportlint.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Blue = Color(0xFF087F72)
private val BlueDark = Color(0xFF176C65)
private val Green = Color(0xFF2E7D32)
private val Amber = Color(0xFFB8860B)
private val Red = Color(0xFFC62828)

val LightColors = lightColorScheme(
    primary = Blue,
    onPrimary = Color.White,
    secondary = BlueDark,
    error = Red,
    background = Color.White,
    surface = Color.White,
    onBackground = Color(0xFF101B38),
    onSurface = Color(0xFF101B38),
)

val DarkColors = darkColorScheme(
    primary = Color(0xFF76D6C3),
    onPrimary = Color(0xFF00382F),
    secondary = Color(0xFF9FCFC5),
    error = Color(0xFFFFB4AB),
)

object ScoreColors {
    val Good = Green
    val Mid = Amber
    val Bad = Red
}

@Composable
fun ReportLintTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, content = content)
}
