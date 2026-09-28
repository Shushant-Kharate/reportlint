@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.reportlint.app.ui.review

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.ui.common.RepositoryViewModelFactory
import com.reportlint.app.ui.common.StatusBadge
import com.reportlint.app.ui.common.UiState

private val SEVERITIES = listOf("ERROR", "WARNING", "INFO")

@Composable
fun ReviewScreen(
    repository: ReportLintRepository,
    templateId: String,
    onBack: () -> Unit,
    onPublished: () -> Unit
) {
    val viewModel: ReviewViewModel = viewModel(
        factory = RepositoryViewModelFactory(repository) { ReviewViewModel(it) }
    )
    val state by viewModel.state.collectAsState()
    val saving by viewModel.saving.collectAsState()
    val saveError by viewModel.saveError.collectAsState()
    var newSectionText by remember { mutableStateOf("") }

    LaunchedEffect(templateId) { viewModel.load(templateId) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Review Template") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        when (val s = state) {
            is UiState.Loading, UiState.Idle -> Box(
                Modifier.fillMaxSize().padding(padding), Alignment.Center
            ) { CircularProgressIndicator() }

            is UiState.Error -> Box(
                Modifier.fillMaxSize().padding(padding), Alignment.Center
            ) { Text("Error: ${s.message}") }

            is UiState.Success -> {
                val data = s.data
                LazyColumn(modifier = Modifier.padding(padding).fillMaxSize()) {
                    item {
                        Column(Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(data.template.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                                Spacer(Modifier.width(8.dp))
                                StatusBadge(data.template.status)
                            }
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "Confirm the values and remove anything that is not a real rule before publishing.",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        HorizontalDivider()
                    }

                    item {
                        SectionHeader("Formatting rules (${data.typographyAndPageRules.size})")
                    }
                    items(data.typographyAndPageRules, key = { it.rule.id }) { er ->
                        FormattingRuleRow(
                            editable = er,
                            onToggle = { viewModel.toggleRuleIncluded(er.rule.id) },
                            onSeverityChange = { viewModel.setRuleSeverity(er.rule.id, it) },
                            onValueChange = { key, value -> viewModel.setExpectedValue(er.rule.id, key, value) }
                        )
                    }

                    item {
                        SectionHeader("Required sections (${data.structureRules.size})")
                    }
                    items(data.structureRules, key = { it.rule.canonicalName }) { es ->
                        StructureRuleRow(
                            editable = es,
                            onToggle = { viewModel.toggleSectionIncluded(es.rule.canonicalName) },
                            onSeverityChange = { viewModel.setSectionSeverity(es.rule.canonicalName, it) }
                        )
                    }

                    item {
                        Row(
                            modifier = Modifier.padding(16.dp).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            OutlinedTextField(
                                value = newSectionText,
                                onValueChange = { newSectionText = it },
                                label = { Text("Add required section") },
                                modifier = Modifier.weight(1f)
                            )
                            Spacer(Modifier.width(8.dp))
                            TextButton(onClick = {
                                viewModel.addSection(newSectionText)
                                newSectionText = ""
                            }) { Text("Add") }
                        }
                    }

                    if (saveError != null) {
                        item {
                            Text(
                                "Save failed: $saveError",
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.padding(16.dp)
                            )
                        }
                    }

                    item {
                        Column(modifier = Modifier.padding(16.dp).fillMaxWidth()) {
                            Button(
                                onClick = { viewModel.save(publish = true, onDone = onPublished) },
                                enabled = !saving, modifier = Modifier.fillMaxWidth()
                            ) { Text(if (saving) "Saving…" else "Publish Template") }
                            Spacer(Modifier.width(12.dp))
                            OutlinedButton(
                                onClick = { viewModel.save(publish = false, onDone = onBack) },
                                enabled = !saving, modifier = Modifier.fillMaxWidth()
                            ) { Text("Save as Draft") }
                        }
                        Spacer(Modifier.height(32.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
    )
}

@Composable
private fun FormattingRuleRow(
    editable: EditableRule,
    onToggle: () -> Unit,
    onSeverityChange: (String) -> Unit,
    onValueChange: (String, String) -> Unit
) {
    Card(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = editable.included, onCheckedChange = { onToggle() })
                Column(Modifier.weight(1f)) {
                    Text(editable.rule.id, fontWeight = FontWeight.Medium)
                    Text(
                        "${editable.rule.type} · ${editable.rule.scope}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                SeverityDropdown(current = editable.severity, onSelect = onSeverityChange)
            }
            if (editable.rule.inferenceNote.isNotBlank()) {
                Text(
                    editable.rule.inferenceNote,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(start = 40.dp, top = 4.dp)
                )
            }
            editable.rule.expectedValue.forEach { (key, value) ->
                var text by remember(editable.rule.id, key) { mutableStateOf(value?.toString() ?: "") }
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it; onValueChange(key, it) },
                    label = { Text(key.replace('_', ' ')) },
                    enabled = editable.included,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                )
            }
        }
    }
}

@Composable
private fun StructureRuleRow(
    editable: EditableSection,
    onToggle: () -> Unit,
    onSeverityChange: (String) -> Unit
) {
    Card(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).fillMaxWidth()) {
        Row(
            Modifier.padding(12.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(checked = editable.included, onCheckedChange = { onToggle() })
            Text(editable.rule.canonicalName, modifier = Modifier.weight(1f))
            SeverityDropdown(
                current = editable.severity,
                onSelect = onSeverityChange,
                options = listOf("ERROR", "WARNING")
            )
        }
    }
}

@Composable
private fun SeverityDropdown(
    current: String,
    onSelect: (String) -> Unit,
    options: List<String> = SEVERITIES
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { expanded = true }) { Text(current) }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { sev ->
                DropdownMenuItem(text = { Text(sev) }, onClick = {
                    onSelect(sev)
                    expanded = false
                })
            }
        }
    }
}
