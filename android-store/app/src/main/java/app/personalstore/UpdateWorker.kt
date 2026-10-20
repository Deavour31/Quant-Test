package app.personalstore

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

/** 주기적으로 새 버전을 확인하고, 있으면 알림을 띄운다. */
class UpdateWorker(private val context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val store = TokenStore(context)
        val token = store.token ?: return Result.success()
        val updates = try {
            GitHubClient(token).listApps().filter { app ->
                val installed = ApkInstaller.installedVersion(context, app.packageName)
                installed != null && app.versionCode > installed
            }
        } catch (e: GitHubException) {
            return if (e.code == 401) Result.success() else Result.retry()
        } catch (_: java.io.IOException) {
            return Result.retry()
        }

        // 같은 업데이트로 매번 알림을 보내지 않도록 목록을 기억해 둔다.
        val signature = updates.joinToString(",") { "${it.packageName}:${it.versionCode}" }
        if (updates.isEmpty() || signature == store.lastNotifiedSignature) return Result.success()
        store.lastNotifiedSignature = signature
        notify(updates)
        return Result.success()
    }

    private fun notify(updates: List<RemoteApp>) {
        val nm = context.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "앱 업데이트", NotificationManager.IMPORTANCE_DEFAULT),
        )
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val names = updates.joinToString(", ") { it.repo.substringAfter('/') }
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("새 업데이트 ${updates.size}개")
            .setContentText(names)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        nm.notify(1, notification)
    }

    private companion object {
        const val CHANNEL = "updates"
    }
}
