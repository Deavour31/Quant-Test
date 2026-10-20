# 내 스토어 (Personal Store)

GitHub 비공개 저장소에 올려 둔 내 안드로이드 앱들을 한곳에서 설치·업데이트하는 개인용 앱스토어.

## 동작 방식
1. 앱에 GitHub 토큰(읽기 전용)을 한 번 입력한다.
2. 토픽 `android-app` 이 붙은 저장소를 자동으로 찾는다.
3. 각 저장소의 **최신 Release** 에 있는 `패키지명_versionCode.apk` 파일을 읽어, 기기에 설치된 버전과 비교한다.
4. [설치] / [업데이트] 버튼으로 APK를 받아 설치한다. 6시간마다 백그라운드로 확인해 새 버전이 있으면 알림을 띄운다.

> 설치 때 시스템 확인 창이 뜨는 것은 안드로이드 정책이라 완전히 없앨 수 없다.

## 처음 한 번만 하는 준비

### 1) 서명 키 만들기 (가장 중요)
모든 버전이 **같은 키**로 서명돼야 업데이트가 덮어써진다. 키는 잃어버리면 복구할 수 없으니 백업해 둔다.
```
keytool -genkeypair -v -keystore release.jks -alias release -keyalg RSA -keysize 2048 -validity 36500
base64 -w0 release.jks     # 이 출력값을 아래 KEYSTORE_BASE64 에 넣는다
```

### 2) 저장소 Secrets 등록
GitHub 저장소 → Settings → Secrets and variables → Actions 에 4개 등록:
`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`

### 3) 스토어 앱 빌드
`store-v1.0.0` 같은 태그를 푸시하면 GitHub Actions가 APK를 빌드해 Release에 올린다.
폰에서 그 APK를 한 번 직접 설치한다. (이후 스토어 앱 자신의 업데이트도 스토어에서 가능 — 이 저장소에 토픽 `android-app` 을 붙일 것)

### 4) 읽기 전용 토큰 발급
GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens**
- Repository access: 내 앱 저장소들 선택
- Permissions: **Contents: Read-only**, Metadata: Read-only
- 발급된 토큰을 스토어 앱에 입력

## 내 앱 저장소를 스토어에 등록하는 법
1. 저장소 메인 페이지 오른쪽 톱니바퀴(About) → Topics 에 `android-app` 추가
2. `templates/android-release.yml` 을 그 저장소의 `.github/workflows/release.yml` 로 복사하고, 위 Secrets 4개를 동일하게 등록
3. 새 버전을 낼 때 태그만 푸시: `git tag v1.2.0 && git push origin v1.2.0`

## 주의
- 이 환경에는 Android SDK가 없어 **아직 빌드/실행 테스트를 하지 못했다.** 첫 빌드에서 오류가 나면 Actions 로그를 보고 수정한다.
- 아이콘은 시스템 기본 아이콘을 쓰고 있다. 필요하면 교체.
