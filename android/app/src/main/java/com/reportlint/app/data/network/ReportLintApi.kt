package com.reportlint.app.data.network

import com.reportlint.app.data.model.ComplianceResult
import com.reportlint.app.data.model.RuleSet
import com.reportlint.app.data.model.Template
import com.reportlint.app.data.model.TemplateSummary
import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path

interface ReportLintApi {

    @Multipart
    @POST("api/templates")
    suspend fun uploadTemplate(
        @Part file: MultipartBody.Part
    ): Template

    @GET("api/templates")
    suspend fun listTemplates(): List<TemplateSummary>

    @GET("api/templates/{id}")
    suspend fun getTemplate(@Path("id") id: String): Template

    @PUT("api/templates/{id}/rules")
    suspend fun updateRules(@Path("id") id: String, @Body ruleset: RuleSet): Template

    @POST("api/templates/{id}/publish")
    suspend fun publishTemplate(@Path("id") id: String): Template

    @DELETE("api/templates/{id}")
    suspend fun deleteTemplate(@Path("id") id: String): Map<String, Boolean>

    @Multipart
    @POST("api/templates/{id}/check")
    suspend fun checkReport(
        @Path("id") id: String,
        @Part report: MultipartBody.Part
    ): ComplianceResult
}
