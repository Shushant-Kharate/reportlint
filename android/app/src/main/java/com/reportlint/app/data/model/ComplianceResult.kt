package com.reportlint.app.data.model

import com.google.gson.annotations.SerializedName

data class Location(
    val section: String? = null,
    @SerializedName("paragraph_index") val paragraphIndex: Int? = null,
    @SerializedName("table_index") val tableIndex: Int? = null,
    @SerializedName("text_preview") val textPreview: String? = null,
    @SerializedName("estimated_page") val estimatedPage: Int? = null
)

data class Violation(
    @SerializedName("rule_id") val ruleId: String,
    val severity: String,
    val category: String,
    val message: String,
    val expected: Map<String, Any?> = emptyMap(),
    val actual: Map<String, Any?>? = null,
    val location: Location = Location(),
    @SerializedName("affected_count") val affectedCount: Int = 1,
    @SerializedName("affected_paragraph_indices") val affectedParagraphIndices: List<Int> = emptyList()
)

data class CategoryScore(
    val category: String,
    val score: Double,
    @SerializedName("checks_performed") val checksPerformed: Int,
    @SerializedName("error_count") val errorCount: Int,
    @SerializedName("warning_count") val warningCount: Int
)

data class ComplianceResult(
    @SerializedName("overall_score") val overallScore: Double,
    @SerializedName("category_scores") val categoryScores: List<CategoryScore> = emptyList(),
    val violations: List<Violation> = emptyList(),
    @SerializedName("total_checks_passed") val totalChecksPassed: Int,
    @SerializedName("total_errors") val totalErrors: Int,
    @SerializedName("total_warnings") val totalWarnings: Int,
    @SerializedName("template_id") val templateId: String? = null,
    @SerializedName("template_name") val templateName: String? = null,
    @SerializedName("template_status") val templateStatus: String? = null,
    @SerializedName("report_filename") val reportFilename: String? = null
)
