package com.reportlint.app.data.model

import com.google.gson.annotations.SerializedName

data class Rule(
    val id: String,
    val type: String,
    val scope: String,
    @SerializedName("section_ref") val sectionRef: String? = null,
    @SerializedName("expected_value") val expectedValue: Map<String, Any?> = emptyMap(),
    val tolerance: Map<String, Any?>? = null,
    val severity: String,
    val weight: Double = 1.0,
    @SerializedName("source_confidence") val sourceConfidence: Double = 0.0,
    @SerializedName("inference_note") val inferenceNote: String = "",
    @SerializedName("teacher_confirmed") val teacherConfirmed: Boolean = false
)

data class RequiredSectionRule(
    @SerializedName("canonical_name") val canonicalName: String,
    val aliases: List<String> = emptyList(),
    val required: Boolean = true,
    @SerializedName("order_index") val orderIndex: Int,
    val parent: String? = null,
    val severity: String = "ERROR"
)

data class RuleSet(
    @SerializedName("template_source_filename") val templateSourceFilename: String,
    @SerializedName("typography_rules") val typographyRules: List<Rule> = emptyList(),
    @SerializedName("paragraph_rules") val paragraphRules: List<Rule> = emptyList(),
    @SerializedName("page_rules") val pageRules: List<Rule> = emptyList(),
    @SerializedName("structure_rules") val structureRules: List<RequiredSectionRule> = emptyList(),
    val version: Int = 1
)
