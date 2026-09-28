package com.reportlint.app.ui.nav

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.compose.*
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.data.repository.ServerConfig
import com.reportlint.app.ui.check.CheckScreen
import com.reportlint.app.ui.review.ReviewScreen
import com.reportlint.app.ui.templates.TemplatesScreen

@Composable
fun AppNav(repository: ReportLintRepository, serverConfig: ServerConfig) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    fun open(target: String) {
        nav.navigate(target) {
            popUpTo(nav.graph.startDestinationId) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }
    Scaffold(bottomBar = {
        if (route?.startsWith("review/") != true) NavigationBar {
            NavigationBarItem(selected = route == "check", onClick = { open("check") },
                icon = { Icon(Icons.Default.Check, null) }, label = { Text("Check") })
            NavigationBarItem(selected = route == "templates", onClick = { open("templates") },
                icon = { Icon(Icons.Default.List, null) }, label = { Text("Templates") })
        }
    }) { padding ->
        NavHost(navController = nav, startDestination = "check", modifier = Modifier.padding(padding)) {
            composable("check") { CheckScreen(repository, onBack = { open("templates") }) }
            composable("templates") {
                TemplatesScreen(repository, serverConfig,
                    onOpenTemplate = { nav.navigate("review/$it") }, onCheckReports = { open("check") })
            }
            composable("review/{templateId}") { backStack ->
                val id = backStack.arguments?.getString("templateId") ?: return@composable
                ReviewScreen(repository, id, onBack = { nav.popBackStack() }, onPublished = { nav.popBackStack() })
            }
        }
    }
}
