package com.reportlint.app.data.model

import com.google.gson.annotations.SerializedName

data class Template(
    val id: String,
    val name: String,
    @SerializedName("source_filename") val sourceFilename: String,
    val status: String,
    val ruleset: RuleSet,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class TemplateSummary(
    val id: String,
    val name: String,
    @SerializedName("source_filename") val sourceFilename: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("rule_count") val ruleCount: Int
)
