package app.personalstore

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.os.Build
import kotlinx.coroutines.flow.MutableSharedFlow
import java.io.File

/** 설치 결과를 화면에 알리기 위한 통로. */
object InstallEvents {
    val messages = MutableSharedFlow<String>(extraBufferCapacity = 8)
}

object ApkInstaller {
    const val ACTION = "app.personalstore.INSTALL_RESULT"

    fun install(context: Context, apk: File) {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        if (Build.VERSION.SDK_INT >= 31) {
            // 스토어가 처음 설치한 앱의 업데이트는 확인 창 없이 진행될 수 있다.
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        }
        val id = installer.createSession(params)
        installer.openSession(id).use { session ->
            apk.inputStream().use { input ->
                session.openWrite("app.apk", 0, apk.length()).use { out ->
                    input.copyTo(out)
                    session.fsync(out)
                }
            }
            val intent = Intent(context, InstallResultReceiver::class.java).setAction(ACTION)
            val pending = PendingIntent.getBroadcast(
                context, id, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
            )
            session.commit(pending.intentSender)
        }
    }

    /** 기기에 설치된 versionCode. 설치돼 있지 않으면 null. */
    fun installedVersion(context: Context, packageName: String): Long? = try {
        context.packageManager.getPackageInfo(packageName, 0).longVersionCode
    } catch (_: PackageManager.NameNotFoundException) {
        null
    }
}

class InstallResultReceiver : BroadcastReceiver() {
    @Suppress("DEPRECATION")
    override fun onReceive(context: Context, intent: Intent) {
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -1)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                // 시스템 설치 확인 창을 띄운다.
                val confirm = if (Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT)
                }
                confirm?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                confirm?.let(context::startActivity)
            }
            PackageInstaller.STATUS_SUCCESS -> InstallEvents.messages.tryEmit("설치가 완료되었습니다.")
            else -> {
                val reason = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "코드 $status"
                InstallEvents.messages.tryEmit("설치 실패: $reason")
            }
        }
    }
}
