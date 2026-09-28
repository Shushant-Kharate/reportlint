@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.reportlint.app.ui.check

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.reportlint.app.data.model.CategoryScore
import com.reportlint.app.data.model.ComplianceResult
import com.reportlint.app.data.model.TemplateSummary
import com.reportlint.app.data.model.Violation
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.ui.common.RepositoryViewModelFactory
import com.reportlint.app.ui.common.SeverityBadge
import com.reportlint.app.ui.common.UiState
import com.reportlint.app.ui.theme.ScoreColors

private val DOCX_MIME = arrayOf(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

@Composable
fun CheckScreen(
    repository: ReportLintRepository,
    onBack: () -> Unit
) {
    val viewModel: CheckViewModel = viewModel(
        factory = RepositoryViewModelFactory(repository) { CheckViewModel(it) }
    )
    val templatesState by viewModel.templates.collectAsState()
    val resultState by viewModel.result.collectAsState()
    var selectedTemplateId by rememberSaveable { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) { viewModel.loadTemplates() }

    val filePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        val templateId = selectedTemplateId
        if (uri != null && templateId != null) {
            viewModel.checkReport(templateId, uri)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Check a Report") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            when (val r = resultState) {
                is UiState.Success -> ResultsView(
                    result = r.data,
                    onCheckAnother = { viewModel.resetResult() }
                )
                is UiState.Loading -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(Modifier.height(12.dp))
                        Text("Checking report against template…")
                    }
                }
                is UiState.Error -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Check failed: ${r.message}")
                        TextButton(onClick = { viewModel.resetResult() }) { Text("Try again") }
                    }
                }
                UiState.Idle -> PickTemplateAndReport(
                    templatesState = templatesState,
                    selectedTemplateId = selectedTemplateId,
                    onSelectTemplate = { selectedTemplateId = it },
                    onPickFile = { filePicker.launch(DOCX_MIME) },
                    onRetry = { viewModel.loadTemplates() }
                )
            }
        }
    }
}

@Composable
private fun PickTemplateAndReport(
    templatesState: UiState<List<TemplateSummary>>,
    selectedTemplateId: String?,
    onSelectTemplate: (String) -> Unit,
    onPickFile: () -> Unit,
    onRetry: () -> Unit
) {
    when (val s = templatesState) {
        is UiState.Loading, UiState.Idle -> Box(Modifier.fillMaxSize(), Alignment.Center) {
            CircularProgressIndicator()
        }
        is UiState.Error -> Box(Modifier.fillMaxSize(), Alignment.Center) {
            Column(Modifier.padding(24.dp)) {
                Text("Couldn't load templates: ${s.message}")
                TextButton(onClick = onRetry) { Text("Try again") }
            }
        }
        is UiState.Success -> {
            if (s.data.isEmpty()) {
                Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Text("No published templates yet. Publish one from the Templates screen first.")
                }
                return
            }
            Column(Modifier.padding(24.dp).verticalScroll(rememberScrollState())) {
                Text("Choose a published template", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                s.data.forEach { t ->
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = selectedTemplateId == t.id,
                            onClick = { onSelectTemplate(t.id) }
                        )
                        Text(t.name)
                    }
                }
                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = onPickFile,
                    enabled = selectedTemplateId != null
                ) { Text("Pick report .docx and check") }
            }
        }
    }
}

@Composable
private fun ResultsView(result: ComplianceResult, onCheckAnother: () -> Unit) {
    val scoreColor = when {
        result.overallScore >= 85 -> ScoreColors.Good
        result.overallScore >= 60 -> ScoreColors.Mid
        else -> ScoreColors.Bad
    }
    LazyColumn(Modifier.fillMaxSize()) {
        item {
            Column(Modifier.padding(16.dp)) {
                Text(result.reportFilename ?: "Report", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(4.dp))
                Text(
                    if (result.categoryScores.sumOf { it.checksPerformed } == 0) "Not scored" else "${result.overallScore}%",
                    color = scoreColor,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.displayMedium
                )
                Text(
                    "${result.totalChecksPassed} checks passed · " +
                        "${result.totalErrors} errors · ${result.totalWarnings} warnings",
                    style = MaterialTheme.typography.bodySmall
                )
            }
            HorizontalDivider()
        }

        item {
            Column(Modifier.padding(16.dp)) {
                Text("By category", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                result.categoryScores.forEach { CategoryRow(it) }
            }
            HorizontalDivider()
        }

        item {
            Text(
                "Violations (${result.violations.size})",
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.padding(16.dp)
            )
        }
        items(result.violations) { v -> ViolationRow(v) }

        item {
            Button(
                onClick = onCheckAnother,
                modifier = Modifier.padding(16.dp)
            ) { Text("Check another report") }
        }
    }
}

@Composable
private fun CategoryRow(c: CategoryScore) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(c.category.replace('_', ' ').lowercase(), modifier = Modifier.weight(1f))
        Text(if (c.checksPerformed == 0) "Not checked" else "${c.score}%")
    }
}

@Composable
private fun ViolationRow(v: Violation) {
    Card(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SeverityBadge(v.severity)
                Spacer(Modifier.width(8.dp))
                Text(v.ruleId, fontWeight = FontWeight.Medium)
            }
            Spacer(Modifier.height(4.dp))
            Text(v.message, style = MaterialTheme.typography.bodyMedium)
            if (v.affectedCount > 1) {
                Text(
                    "${v.affectedCount} occurrences",
                    style = MaterialTheme.typography.bodySmall
                )
            }
            v.location.textPreview?.let {
                Text(
                    "\"$it\"",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }
        }
    }
}
