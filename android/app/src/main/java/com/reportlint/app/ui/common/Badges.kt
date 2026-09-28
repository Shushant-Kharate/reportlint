package com.reportlint.app.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun Badge(text: String, background: Color, foreground: Color, modifier: Modifier = Modifier) {
    Text(
        text = text,
        color = foreground,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = modifier
            .background(background, RoundedCornerShape(10.dp))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    )
}

@Composable
fun severityColors(severity: String): Pair<Color, Color> = when (severity) {
    "ERROR" -> Color(0xFFF8D7DA) to Color(0xFF721C24)
    "WARNING" -> Color(0xFFFFF3CD) to Color(0xFF856404)
    else -> Color(0xFFE2E3E5) to Color(0xFF383D41)
}

@Composable
fun statusColors(status: String): Pair<Color, Color> = when (status) {
    "PUBLISHED" -> Color(0xFFD4EDDA) to Color(0xFF155724)
    else -> Color(0xFFFFF3CD) to Color(0xFF856404)
}

@Composable
fun SeverityBadge(severity: String) {
    val (bg, fg) = severityColors(severity)
    Badge(text = severity, background = bg, foreground = fg)
}

@Composable
fun StatusBadge(status: String) {
    val (bg, fg) = statusColors(status)
    Badge(text = status, background = bg, foreground = fg)
}
