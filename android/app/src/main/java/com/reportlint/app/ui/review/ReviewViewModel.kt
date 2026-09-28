package com.reportlint.app.ui.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reportlint.app.data.model.RequiredSectionRule
import com.reportlint.app.data.model.Rule
import com.reportlint.app.data.model.RuleSet
import com.reportlint.app.data.model.Template
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.ui.common.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Editable working copy of a template's rules. Mirrors the same "teacher
 * review" contract as the Stage 2 web frontend's review.html: every
 * formatting rule can be included/excluded and re-severitized, structure
 * rules can be deselected (fixes over-firing false positives like title
 * page lines becoming "required sections") or added freehand.
 */
data class EditableRule(
    val rule: Rule,
    val included: Boolean,
    val severity: String
)

data class EditableSection(
    val rule: RequiredSectionRule,
    val included: Boolean,
    val severity: String
)

data class ReviewUiState(
    val template: Template,
    val typographyAndPageRules: List<EditableRule>,
    val structureRules: List<EditableSection>
)

class ReviewViewModel(private val repository: ReportLintRepository) : ViewModel() {

    private val _state = MutableStateFlow<UiState<ReviewUiState>>(UiState.Idle)
    val state: StateFlow<UiState<ReviewUiState>> = _state.asStateFlow()

    private val _saving = MutableStateFlow(false)
    val saving: StateFlow<Boolean> = _saving.asStateFlow()

    private val _saveError = MutableStateFlow<String?>(null)
    val saveError: StateFlow<String?> = _saveError.asStateFlow()

    fun load(templateId: String) {
        viewModelScope.launch {
            _state.value = UiState.Loading
            repository.getTemplate(templateId).fold(
                onSuccess = { t -> _state.value = UiState.Success(toEditable(t)) },
                onFailure = { _state.value = UiState.Error(it.message ?: "Failed to load template") }
            )
        }
    }

    private fun toEditable(t: Template): ReviewUiState {
        val formattingRules = (t.ruleset.typographyRules + t.ruleset.paragraphRules + t.ruleset.pageRules).map {
            EditableRule(rule = it, included = it.severity != "INFO", severity = it.severity)
        }
        val structureRules = t.ruleset.structureRules.map {
            EditableSection(rule = it, included = true, severity = it.severity)
        }
        return ReviewUiState(t, formattingRules, structureRules)
    }

    fun setExpectedValue(ruleId: String, key: String, text: String) = updateState { s ->
        s.copy(typographyAndPageRules = s.typographyAndPageRules.map { er ->
            if (er.rule.id != ruleId) er else {
                val value: Any? = when (key) {
                    "font", "alignment" -> text
                    "bold", "italic" -> text.toBooleanStrictOrNull() ?: text
                    else -> text.toDoubleOrNull() ?: text
                }
                er.copy(rule = er.rule.copy(expectedValue = er.rule.expectedValue + (key to value)))
            }
        })
    }

    fun toggleRuleIncluded(ruleId: String) = updateState { s ->
        s.copy(typographyAndPageRules = s.typographyAndPageRules.map {
            if (it.rule.id == ruleId) it.copy(included = !it.included) else it
        })
    }

    fun setRuleSeverity(ruleId: String, severity: String) = updateState { s ->
        s.copy(typographyAndPageRules = s.typographyAndPageRules.map {
            if (it.rule.id == ruleId) it.copy(severity = severity) else it
        })
    }

    fun toggleSectionIncluded(canonicalName: String) = updateState { s ->
        s.copy(structureRules = s.structureRules.map {
            if (it.rule.canonicalName == canonicalName) it.copy(included = !it.included) else it
        })
    }

    fun setSectionSeverity(canonicalName: String, severity: String) = updateState { s ->
        s.copy(structureRules = s.structureRules.map {
            if (it.rule.canonicalName == canonicalName) it.copy(severity = severity) else it
        })
    }

    fun addSection(name: String) = updateState { s ->
        val normalized = name.trim().lowercase()
        if (normalized.isEmpty() || s.structureRules.any { it.rule.canonicalName == normalized }) return@updateState s
        val newRule = RequiredSectionRule(
            canonicalName = normalized,
            aliases = emptyList(),
            required = true,
            orderIndex = s.structureRules.size,
            parent = null,
            severity = "ERROR"
        )
        s.copy(structureRules = s.structureRules + EditableSection(newRule, included = true, severity = "ERROR"))
    }

    private fun updateState(transform: (ReviewUiState) -> ReviewUiState) {
        val current = _state.value
        if (current is UiState.Success) {
            _state.value = UiState.Success(transform(current.data))
        }
    }

    fun save(publish: Boolean, onDone: () -> Unit) {
        if (_saving.value) return
        val current = _state.value
        if (current !is UiState.Success) return
        val s = current.data

        val includedFormatting = s.typographyAndPageRules.filter { it.included }
            .map { it.rule.copy(severity = it.severity, teacherConfirmed = true) }
        val paragraphTypes = setOf("ALIGNMENT", "LINE_SPACING_MULTIPLE", "LINE_SPACING_EXACT", "SPACING_BEFORE", "SPACING_AFTER", "INDENTATION")
        val typo = includedFormatting.filter { it.type !in paragraphTypes && it.type != "PAGE_SIZE" && it.type != "MARGIN" }
        val page = includedFormatting.filter { it.type == "PAGE_SIZE" || it.type == "MARGIN" }
        val structure = s.structureRules.filter { it.included }
            .mapIndexed { idx, es -> es.rule.copy(severity = es.severity, orderIndex = idx) }

        val newRuleset = RuleSet(
            templateSourceFilename = s.template.ruleset.templateSourceFilename,
            typographyRules = typo,
            paragraphRules = includedFormatting.filter { it.type in paragraphTypes },
            pageRules = page,
            structureRules = structure,
            version = s.template.ruleset.version
        )

        viewModelScope.launch {
            _saving.value = true
            _saveError.value = null
            val updateResult = repository.updateRules(s.template.id, newRuleset)
            updateResult.fold(
                onSuccess = {
                    if (publish) {
                        repository.publishTemplate(s.template.id).fold(
                            onSuccess = { _saving.value = false; onDone() },
                            onFailure = { _saving.value = false; _saveError.value = it.message }
                        )
                    } else {
                        _saving.value = false
                        onDone()
                    }
                },
                onFailure = { _saving.value = false; _saveError.value = it.message }
            )
        }
    }
}
