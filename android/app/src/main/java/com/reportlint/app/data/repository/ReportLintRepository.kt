package com.reportlint.app.data.repository

import android.content.Context
import android.net.Uri
import com.reportlint.app.data.model.ComplianceResult
import com.reportlint.app.data.model.RuleSet
import com.reportlint.app.data.model.Template
import com.reportlint.app.data.model.TemplateSummary
import com.reportlint.app.data.network.ApiClient
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext

class ReportLintRepository(
    private val context: Context,
    private val serverConfig: ServerConfig
) {
    private suspend fun api() = ApiClient.create(serverConfig.serverUrl.first())

    suspend fun uploadTemplate(uri: Uri): Result<Template> = withContext(Dispatchers.IO) {
        request {
            withUpload(context, uri, "file") { part -> api().uploadTemplate(part) }
        }
    }

    suspend fun listTemplates(): Result<List<TemplateSummary>> = withContext(Dispatchers.IO) {
        request { api().listTemplates() }
    }

    suspend fun getTemplate(id: String): Result<Template> = withContext(Dispatchers.IO) {
        request { api().getTemplate(id) }
    }

    suspend fun updateRules(id: String, ruleset: RuleSet): Result<Template> = withContext(Dispatchers.IO) {
        request { api().updateRules(id, ruleset) }
    }

    suspend fun publishTemplate(id: String): Result<Template> = withContext(Dispatchers.IO) {
        request { api().publishTemplate(id) }
    }

    suspend fun deleteTemplate(id: String): Result<Unit> = withContext(Dispatchers.IO) {
        request { api().deleteTemplate(id); Unit }
    }

    suspend fun checkReport(templateId: String, uri: Uri): Result<ComplianceResult> =
        withContext(Dispatchers.IO) {
            request {
                withUpload(context, uri, "report") { part -> api().checkReport(templateId, part) }
            }
        }
}

private suspend fun <T> request(block: suspend () -> T): Result<T> = try {
    Result.success(block())
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (error: Exception) {
    val detail = if (error is HttpException) {
        runCatching {
            val json = JsonParser.parseString(error.response()?.errorBody()?.string() ?: "{}").asJsonObject
            json.get("detail")?.takeIf { it.isJsonPrimitive }?.asString
        }.getOrNull()
    } else null
    Result.failure(IllegalStateException(detail ?: error.message ?: "Request failed. Please try again.", error))
}
