package app.personalstore

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException
import java.net.HttpURLConnection
import java.net.URL

/** 저장소 하나의 최신 릴리스에서 읽어 낸 앱 정보. */
data class RemoteApp(
    val repo: String,
    val tag: String,
    val packageName: String,
    val versionCode: Long,
    val assetApiUrl: String,
    val size: Long,
)

class GitHubException(val code: Int, message: String) : Exception(message)

/**
 * 규칙
 *  - 저장소에 토픽 `android-app` 이 붙어 있어야 목록에 나온다.
 *  - 최신 Release 에 `<패키지명>_<versionCode>.apk` 형식의 파일이 있어야 한다.
 *    (예: com.example.memo_12.apk)  → APK 를 내려받지 않고도 버전을 비교할 수 있다.
 */
class GitHubClient(private val token: String) {

    suspend fun listApps(): List<RemoteApp> = coroutineScope {
        listAppRepos().map { repo -> async(Dispatchers.IO) { latestApp(repo) } }.awaitAll().filterNotNull()
    }

    private suspend fun listAppRepos(): List<String> = withContext(Dispatchers.IO) {
        val result = mutableListOf<String>()
        var page = 1
        while (true) {
            val url = "$API/user/repos?per_page=100&page=$page&sort=updated" +
                "&affiliation=owner,collaborator,organization_member"
            val arr = JSONArray(getText(url))
            if (arr.length() == 0) break
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                val topics = r.optJSONArray("topics") ?: continue
                val tagged = (0 until topics.length()).any { topics.getString(it) == TOPIC }
                if (tagged && !r.optBoolean("archived")) result += r.getString("full_name")
            }
            page++
        }
        result
    }

    private fun latestApp(repo: String): RemoteApp? {
        val json = try {
            JSONObject(getText("$API/repos/$repo/releases/latest"))
        } catch (e: GitHubException) {
            if (e.code == 404) return null // 릴리스가 아직 없는 저장소
            throw e
        }
        val assets = json.optJSONArray("assets") ?: return null
        for (i in 0 until assets.length()) {
            val a = assets.getJSONObject(i)
            val m = ASSET_NAME.matchEntire(a.getString("name")) ?: continue
            return RemoteApp(
                repo = repo,
                tag = json.getString("tag_name"),
                packageName = m.groupValues[1],
                versionCode = m.groupValues[2].toLong(),
                assetApiUrl = a.getString("url"),
                size = a.optLong("size"),
            )
        }
        return null
    }

    /** 비공개 저장소의 APK 를 받는다. GitHub 는 저장소 서버(S3 등)로 리다이렉트하는데, 그쪽에는 토큰을 보내면 안 된다. */
    suspend fun download(app: RemoteApp, dest: File, onProgress: (Float) -> Unit) = withContext(Dispatchers.IO) {
        var url = app.assetApiUrl
        var sendToken = true
        repeat(MAX_REDIRECTS) {
            val conn = open(url).apply {
                instanceFollowRedirects = false
                setRequestProperty("Accept", "application/octet-stream")
                if (sendToken) setRequestProperty("Authorization", "Bearer $token")
            }
            val code = conn.responseCode
            if (code in 300..399) {
                url = conn.getHeaderField("Location") ?: throw GitHubException(code, "리다이렉트 주소 없음")
                sendToken = false
                conn.disconnect()
                return@repeat
            }
            if (code !in 200..299) throw GitHubException(code, "다운로드 실패 ($code)")
            val total = conn.contentLengthLong.takeIf { it > 0 } ?: app.size
            conn.inputStream.use { input ->
                dest.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        done += n
                        if (total > 0) onProgress((done.toFloat() / total).coerceIn(0f, 1f))
                    }
                }
            }
            return@withContext
        }
        throw GitHubException(0, "리다이렉트가 너무 많음")
    }

    private fun open(url: String) = (URL(url).openConnection() as HttpURLConnection).apply {
        connectTimeout = 15_000
        readTimeout = 30_000
    }

    private fun getText(url: String): String {
        val conn = open(url).apply {
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
        }
        try {
            val code = conn.responseCode
            if (code !in 200..299) {
                val msg = when (code) {
                    401 -> "토큰이 올바르지 않거나 만료되었습니다."
                    403 -> "접근이 거부되었거나 API 사용 한도를 넘었습니다."
                    else -> "GitHub 오류 ($code)"
                }
                throw GitHubException(code, msg)
            }
            return conn.inputStream.bufferedReader().use { it.readText() }
        } catch (e: FileNotFoundException) {
            throw GitHubException(404, "찾을 수 없음")
        } finally {
            conn.disconnect()
        }
    }

    companion object {
        const val TOPIC = "android-app"
        private const val API = "https://api.github.com"
        private const val MAX_REDIRECTS = 5
        private val ASSET_NAME = Regex("""(.+)_(\d+)\.apk""")
    }
}
