package com.reportlint.app

import android.app.Application
import com.reportlint.app.data.repository.ReportLintRepository
import com.reportlint.app.data.repository.ServerConfig

class ReportLintApp : Application() {
    lateinit var serverConfig: ServerConfig
        private set
    lateinit var repository: ReportLintRepository
        private set

    override fun onCreate() {
        super.onCreate()
        serverConfig = ServerConfig(this)
        repository = ReportLintRepository(this, serverConfig)
    }
}
