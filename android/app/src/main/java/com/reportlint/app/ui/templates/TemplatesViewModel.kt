package com.reportlint.app.ui.templates

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reportlint.app.data.model.Template
import com.reportlint.app.data.model.TemplateSummary
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.ui.common.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TemplatesViewModel(private val repository: ReportLintRepository) : ViewModel() {

    private val _state = MutableStateFlow<UiState<List<TemplateSummary>>>(UiState.Idle)
    val state: StateFlow<UiState<List<TemplateSummary>>> = _state.asStateFlow()

    private val _uploadState = MutableStateFlow<UiState<Template>>(UiState.Idle)
    val uploadState: StateFlow<UiState<Template>> = _uploadState.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            repository.listTemplates().fold(
                onSuccess = { _state.value = UiState.Success(it) },
                onFailure = { _state.value = UiState.Error(it.message ?: "Failed to load templates") }
            )
        }
    }

    fun upload(uri: Uri) {
        if (_uploadState.value is UiState.Loading) return
        viewModelScope.launch {
            _uploadState.value = UiState.Loading
            repository.uploadTemplate(uri).fold(
                onSuccess = {
                    _uploadState.value = UiState.Success(it)
                    load()
                },
                onFailure = { _uploadState.value = UiState.Error(it.message ?: "Upload failed") }
            )
        }
    }

    fun consumeUploadResult() {
        _uploadState.value = UiState.Idle
    }

    fun delete(id: String) {
        viewModelScope.launch {
            repository.deleteTemplate(id).fold(
                onSuccess = { load() },
                onFailure = { _state.value = UiState.Error(it.message ?: "Delete failed") }
            )
        }
    }
}
