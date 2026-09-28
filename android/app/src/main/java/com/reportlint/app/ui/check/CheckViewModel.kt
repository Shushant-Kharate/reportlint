package com.reportlint.app.ui.check

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reportlint.app.data.model.ComplianceResult
import com.reportlint.app.data.model.TemplateSummary
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.ui.common.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CheckViewModel(private val repository: ReportLintRepository) : ViewModel() {

    private val _templates = MutableStateFlow<UiState<List<TemplateSummary>>>(UiState.Idle)
    val templates: StateFlow<UiState<List<TemplateSummary>>> = _templates.asStateFlow()

    private val _result = MutableStateFlow<UiState<ComplianceResult>>(UiState.Idle)
    val result: StateFlow<UiState<ComplianceResult>> = _result.asStateFlow()

    fun loadTemplates() {
        viewModelScope.launch {
            _templates.value = UiState.Loading
            repository.listTemplates().fold(
                onSuccess = { list ->
                    _templates.value = UiState.Success(list.filter { it.status == "PUBLISHED" })
                },
                onFailure = { _templates.value = UiState.Error(it.message ?: "Failed to load templates") }
            )
        }
    }

    fun checkReport(templateId: String, uri: Uri) {
        if (_result.value is UiState.Loading) return
        viewModelScope.launch {
            _result.value = UiState.Loading
            repository.checkReport(templateId, uri).fold(
                onSuccess = { _result.value = UiState.Success(it) },
                onFailure = { _result.value = UiState.Error(it.message ?: "Check failed") }
            )
        }
    }

    fun resetResult() {
        _result.value = UiState.Idle
    }
}
