@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.reportlint.app.ui.templates

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.reportlint.app.data.model.TemplateSummary
import com.reportlint.app.data.repository.DEFAULT_SERVER_URL
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.data.repository.ServerConfig
import com.reportlint.app.ui.common.RepositoryViewModelFactory
import com.reportlint.app.ui.common.ServerSettingsDialog
import com.reportlint.app.ui.common.StatusBadge
import com.reportlint.app.ui.common.UiState
import kotlinx.coroutines.launch

private val DOCX_MIME = arrayOf(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

@Composable
fun TemplatesScreen(
    repository: ReportLintRepository,
    serverConfig: ServerConfig,
    onOpenTemplate: (String) -> Unit,
    onCheckReports: () -> Unit
) {
    val viewModel: TemplatesViewModel = viewModel(
        factory = RepositoryViewModelFactory(repository) { TemplatesViewModel(it) }
    )
    val state by viewModel.state.collectAsState()
    val uploadState by viewModel.uploadState.collectAsState()
    val scope = rememberCoroutineScope()
    val serverUrl by serverConfig.serverUrl.collectAsState(initial = DEFAULT_SERVER_URL)
    var showSettings by remember { mutableStateOf(false) }
    var deleteId by remember { mutableStateOf<String?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    val filePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri -> uri?.let { viewModel.upload(it) } }

    LaunchedEffect(Unit) { viewModel.load() }

    LaunchedEffect(uploadState) {
        when (val s = uploadState) {
            is UiState.Success -> {
                viewModel.consumeUploadResult()
                onOpenTemplate(s.data.id)
            }
            is UiState.Error -> {
                snackbarHostState.showSnackbar("Upload failed: ${s.message}")
                viewModel.consumeUploadResult()
            }
            else -> {}
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("ReportLint") },
                actions = {
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Filled.Settings, contentDescription = "Server settings")
                    }
                }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { if (uploadState !is UiState.Loading) filePicker.launch(DOCX_MIME) },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text("Upload format") }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {

            OutlinedButton(
                onClick = onCheckReports,
                modifier = Modifier.fillMaxWidth().padding(16.dp)
            ) { Text("Check a report against a published template") }

            if (uploadState is UiState.Loading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(
                    "Analyzing template (parsing DOCX, resolving styles, extracting rules)…",
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodySmall
                )
            }

            when (val s = state) {
                is UiState.Loading -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    CircularProgressIndicator()
                }
                is UiState.Error -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(Modifier.padding(24.dp)) {
                        Text("Couldn't reach the server: ${s.message}")
                        TextButton(onClick = { viewModel.load() }) { Text("Try again") }
                    }
                }
                is UiState.Success -> TemplateList(
                    templates = s.data,
                    onOpen = onOpenTemplate,
                    onDelete = { deleteId = it }
                )
                UiState.Idle -> {}
            }
        }
    }

    if (deleteId != null) {
        AlertDialog(onDismissRequest = { deleteId = null },
            title = { Text("Delete template?") },
            text = { Text("This cannot be undone.") },
            confirmButton = { TextButton(onClick = { deleteId?.let { viewModel.delete(it) }; deleteId = null }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { deleteId = null }) { Text("Cancel") } })
    }
    if (showSettings) {
        ServerSettingsDialog(
            currentUrl = serverUrl,
            onDismiss = { showSettings = false },
            onSave = { newUrl ->
                scope.launch {
                    serverConfig.setServerUrl(newUrl)
                    showSettings = false
                    viewModel.load()
                }
            }
        )
    }
}

@Composable
private fun TemplateList(
    templates: List<TemplateSummary>,
    onOpen: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    if (templates.isEmpty()) {
        Box(Modifier.fillMaxSize(), Alignment.Center) {
            Text("No templates yet. Tap \"Upload format\" to analyze one.")
        }
        return
    }
    LazyColumn(modifier = Modifier.padding(horizontal = 16.dp)) {
        items(templates, key = { it.id }) { t ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                onClick = { onOpen(t.id) }
            ) {
                Row(
                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(t.name, style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            StatusBadge(t.status)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "${t.ruleCount} rules extracted",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                    IconButton(onClick = { onDelete(t.id) }) {
                        Icon(Icons.Filled.Delete, contentDescription = "Delete template")
                    }
                }
            }
        }
        item { Spacer(Modifier.height(80.dp)) } // room for the FAB
    }
}
