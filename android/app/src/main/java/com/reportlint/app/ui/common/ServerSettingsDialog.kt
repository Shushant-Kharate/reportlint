package com.reportlint.app.ui.common

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ServerSettingsDialog(
    currentUrl: String,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit
) {
    var text by remember(currentUrl) { mutableStateOf(currentUrl) }

    val parsed = text.trim().toHttpUrlOrNull()
    val valid = parsed != null && parsed.username.isEmpty() && parsed.password.isEmpty() && parsed.query == null && parsed.fragment == null

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Server address") },
        text = {
            Column {
                Text(
                    "Emulator talking to a FastAPI server on your machine: keep " +
                        "10.0.2.2. Real device on the same Wi-Fi: use your computer's " +
                        "LAN IP instead, e.g. http://192.168.1.23:8000/"
                )
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    label = { Text("Base URL") },
                    singleLine = true,
                    modifier = Modifier.padding(top = 12.dp)
                )
            }
        },
        confirmButton = {
            TextButton(enabled = valid, onClick = { onSave(text.trim()) }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}
