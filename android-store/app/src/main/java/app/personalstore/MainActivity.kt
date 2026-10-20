package app.personalstore

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    private val vm: StoreViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                val notifPermission = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) {}
                LaunchedEffect(Unit) {
                    if (Build.VERSION.SDK_INT >= 33) notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
                StoreScreen(vm, onInstall = ::installWithPermission)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // 설정 화면이나 설치 확인 창에서 돌아오면 최신 상태로 갱신한다.
        if (vm.state.value.hasToken) vm.refresh()
    }

    private fun installWithPermission(row: AppRow) {
        if (!packageManager.canRequestPackageInstalls()) {
            // "이 앱에서 설치 허용"을 켜야 한다. 최초 1회.
            startActivity(
                Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")),
            )
            return
        }
        vm.install(row)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StoreScreen(vm: StoreViewModel, onInstall: (AppRow) -> Unit) {
    val state by vm.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            vm.consumeMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("내 스토어") },
                actions = {
                    if (state.hasToken) {
                        TextButton(onClick = vm::refresh, enabled = !state.loading) { Text("새로고침") }
                        TextButton(onClick = vm::logout) { Text("로그아웃") }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (!state.hasToken) {
                TokenScreen(onSave = vm::saveToken)
            } else {
                if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (state.apps.isEmpty() && !state.loading) {
                    Text(
                        "표시할 앱이 없습니다.\n저장소에 'android-app' 토픽을 붙이고, 릴리스에 APK를 올려 주세요.",
                        Modifier.padding(24.dp),
                    )
                }
                LazyColumn(
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.apps, key = { it.remote.packageName }) { row ->
                        AppCard(row, onInstall)
                    }
                }
            }
        }
    }
}

@Composable
private fun TokenScreen(onSave: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("GitHub 토큰을 입력하세요", style = MaterialTheme.typography.titleMedium)
        Text("읽기 전용(Contents: Read) 권한의 Fine-grained 토큰이면 충분합니다. 토큰은 이 기기 안에 암호화되어 저장됩니다.")
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            label = { Text("토큰") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = { onSave(text) }, enabled = text.isNotBlank()) { Text("연결") }
    }
}

@Composable
private fun AppCard(row: AppRow, onInstall: (AppRow) -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(row.remote.repo.substringAfter('/'), style = MaterialTheme.typography.titleMedium)
                    val installedText = row.installed?.let { "설치됨 v$it → " } ?: ""
                    Text(
                        "$installedText 최신 ${row.remote.tag} (${row.remote.versionCode})",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                when (row.status) {
                    AppStatus.NOT_INSTALLED -> Button(onClick = { onInstall(row) }, enabled = row.progress == null) { Text("설치") }
                    AppStatus.UPDATE -> Button(onClick = { onInstall(row) }, enabled = row.progress == null) { Text("업데이트") }
                    AppStatus.UP_TO_DATE -> OutlinedButton(onClick = {}, enabled = false) { Text("최신") }
                }
            }
            row.progress?.let { LinearProgressIndicator(progress = { it }, modifier = Modifier.fillMaxWidth()) }
        }
    }
}
