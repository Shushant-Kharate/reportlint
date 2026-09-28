package com.reportlint.app.data.repository

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

suspend fun <T> withUpload(context: Context, uri: Uri, field: String, action: suspend (MultipartBody.Part) -> T): T {
    val filename = (queryDisplayName(context, uri) ?: "upload.docx").substringAfterLast('/').substringAfterLast('\\')
    require(filename.endsWith(".docx", ignoreCase = true)) { "Choose a Word .docx file." }
    val cacheFile = File.createTempFile("reportlint_", ".docx", context.cacheDir)
    try {
        context.contentResolver.openInputStream(uri)?.use { input ->
            cacheFile.outputStream().use { output ->
                val buffer = ByteArray(65536)
                var total = 0L
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    require(total <= 20L * 1024 * 1024) { "Choose a document up to 20 MB." }
                    output.write(buffer, 0, count)
                }
                require(total > 0) { "The selected file is empty." }
            }
        } ?: error("Could not open the selected document.")
        val body = cacheFile.asRequestBody("application/vnd.openxmlformats-officedocument.wordprocessingml.document".toMediaType())
        return action(MultipartBody.Part.createFormData(field, filename, body))
    } finally {
        cacheFile.delete()
    }
}

private fun queryDisplayName(context: Context, uri: Uri): String? {
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (index >= 0 && cursor.moveToFirst()) return cursor.getString(index)
    }
    return null
}
