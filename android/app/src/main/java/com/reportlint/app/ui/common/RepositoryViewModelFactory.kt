package com.reportlint.app.ui.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras
import com.reportlint.app.data.repository.ReportLintRepository

class RepositoryViewModelFactory(
    private val repository: ReportLintRepository,
    private val create: (ReportLintRepository) -> ViewModel
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T {
        return create(repository) as T
    }
}
