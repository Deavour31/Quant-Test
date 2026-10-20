package app.personalstore

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import java.io.IOException

enum class AppStatus { NOT_INSTALLED, UPDATE, UP_TO_DATE }

data class AppRow(val remote: RemoteApp, val installed: Long?, val progress: Float? = null) {
    val status: AppStatus
        get() = when {
            installed == null -> AppStatus.NOT_INSTALLED
            remote.versionCode > installed -> AppStatus.UPDATE
            else -> AppStatus.UP_TO_DATE
        }
}

data class StoreState(
    val hasToken: Boolean = false,
    val loading: Boolean = false,
    val apps: List<AppRow> = emptyList(),
    val message: String? = null,
)

class StoreViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)
    private val _state = MutableStateFlow(StoreState(hasToken = tokenStore.token != null))
    val state: StateFlow<StoreState> = _state

    init {
        if (_state.value.hasToken) refresh()
        viewModelScope.launch {
            InstallEvents.messages.collect { msg ->
                _state.update { it.copy(message = msg) }
                if (msg.startsWith("설치가 완료")) refresh()
            }
        }
    }

    fun saveToken(token: String) {
        tokenStore.token = token.trim()
        _state.update { it.copy(hasToken = true, message = null) }
        refresh()
    }

    fun logout() {
        tokenStore.token = null
        _state.value = StoreState()
    }

    fun consumeMessage() = _state.update { it.copy(message = null) }

    fun refresh() {
        val token = tokenStore.token ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, message = null) }
            try {
                val ctx = getApplication<Application>()
                val rows = GitHubClient(token).listApps()
                    .map { AppRow(it, ApkInstaller.installedVersion(ctx, it.packageName)) }
                    .sortedBy { it.remote.repo }
                _state.update { it.copy(apps = rows, loading = false) }
            } catch (e: GitHubException) {
                if (e.code == 401) tokenStore.token = null
                _state.update {
                    it.copy(loading = false, hasToken = e.code != 401, message = e.message)
                }
            } catch (e: IOException) {
                _state.update { it.copy(loading = false, message = "네트워크 오류: ${e.message}") }
            }
        }
    }

    fun install(row: AppRow) {
        val token = tokenStore.token ?: return
        val ctx = getApplication<Application>()
        viewModelScope.launch {
            val dir = File(ctx.cacheDir, "apks").apply { mkdirs() }
            val file = File(dir, "${row.remote.packageName}.apk")
            try {
                setProgress(row, 0f)
                GitHubClient(token).download(row.remote, file) { setProgress(row, it) }
                ApkInstaller.install(ctx, file)
            } catch (e: GitHubException) {
                _state.update { it.copy(message = e.message) }
            } catch (e: IOException) {
                _state.update { it.copy(message = "다운로드 실패: ${e.message}") }
            } finally {
                setProgress(row, null)
            }
        }
    }

    private fun setProgress(row: AppRow, value: Float?) = _state.update { s ->
        s.copy(apps = s.apps.map {
            if (it.remote.packageName == row.remote.packageName) it.copy(progress = value) else it
        })
    }
}
