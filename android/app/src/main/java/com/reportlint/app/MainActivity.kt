package com.reportlint.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.reportlint.app.ui.nav.AppNav
import com.reportlint.app.ui.theme.ReportLintTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as ReportLintApp

        setContent {
            ReportLintTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    AppNav(repository = app.repository, serverConfig = app.serverConfig)
                }
            }
        }
    }
}
