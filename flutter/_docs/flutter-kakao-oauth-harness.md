# 인증 시스템 구현 명세 — Flutter 클라이언트 (Kakao OAuth + 자체 JWT)

> 원 명세는 사용자가 전달한 "인증 시스템 구현 명세"다. 이 문서는 그 명세를 **이 저장소의 실제
> Flutter 앱과 대조해** 모바일 클라이언트 몫으로 확정한 작업 명세다. 서버 몫은
> [[minseok/_docs/flutter-kakao-oauth-harness|백엔드 kakao oauth harness]]에 있다.
>
> **진행 상황(2026-08-03):** 앱 쪽 화면·세션 코드는 작성했다(5절 참조). 다만 서버의
> `/auth/mobile/*` 엔드포인트는 **아직 없으므로 실제 로그인은 성공하지 못한다** —
> 카카오 인증까지는 통과하고 서버 호출에서 실패한다. 백엔드 문서 3절(C1~C9) 결정이 먼저다.

관련: [[flutter/_docs/flutter-harness|flutter harness]] · [[CLAUDE|루트 CLAUDE]]

---

## 1. 앱 현황 실측 (2026-08-03, 파일 직접 확인)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| Flutter / Dart | 3.44.8 / 3.12.2 (SDK 제약 `^3.12.2`) | [[flutter/_docs/flutter-harness\|flutter harness]] · `pubspec.yaml` |
| 앱 식별자 | Android `com.redoceanmap.app` · iOS `com.redoceanmap.app` | `android/app/build.gradle.kts:19` · `ios/…/project.pbxproj:385` |
| minSdk | Flutter 기본값 **24** (Android 7.0) | `build.gradle.kts:22` |
| 의존성 | `http` · `video_player` · `cupertino_icons` 뿐 | `pubspec.yaml` |
| 화면 | `intro` → `home` → `workspace` · `stopwatch` | `lib/*.dart` (총 8파일) |
| API 베이스 | `https://api.redoceanmap.com` **직결** (rewrite 없음) | `lib/api.dart:9` |
| 인증 | **없음.** `askChat`은 401을 그대로 받는다(`ApiException.needsLogin`만 존재) | `lib/api.dart:95,109` |
| 토큰 저장소 | 없음 | — |

**즉, 로그인 관련 코드는 전무하다.** 명세 8절 첫 항목("`UserApi.instance.me()` 호출이 존재하지
않는다")은 현재 자동으로 만족하지만, 구현 중에 **깨지기 쉬운 지점**이므로 6절에서 검증 명령으로 고정한다.

---

## 2. 절대 규칙 (명세 2장 — 변경 금지)

1. **`UserApi.instance.me()`를 앱에서 호출하지 않는다.** SDK의 `loginWithKakaoTalk()` /
   `loginWithKakaoAccount()`는 `OAuthToken`만 반환하며, 프로필 조회는 별도 호출이다.
   앱은 **토큰만 서버로 넘기고 프로필은 서버가 카카오에서 직접 받는다.**
2. **프로필(닉네임·이메일 등)을 서버로 보내지 않는다.** 클라이언트가 보낸 유저 정보는 서버가
   신뢰하지 않는다. 요청 body는 `{ accessToken, deviceId }` **두 필드뿐**이다.
3. **카카오 토큰을 저장하지 않는다.** 서버 응답(자체 JWT)을 받은 뒤 메모리에서 버린다.
   `flutter_secure_storage`에 넣는 것은 **자체 리프레시 토큰뿐**이다.
4. **카카오 토큰은 POST body로만 보낸다.** 쿼리 파라미터 금지(액세스 로그에 남는다).

---

## 3. 착수 전 결정·준비가 필요한 것 ★

### P1. 카카오 콘솔 준비물 (코드보다 먼저)

| 준비물 | 값 | 비고 |
| --- | --- | --- |
| **네이티브 앱 키** | 콘솔 → 앱 설정 → 앱 키 | 서버가 쓰는 **REST API 키(`KAKAO_CLIENT_ID`)와 다른 값**이다 |
| **앱 ID(`app_id`)** | 콘솔 → 앱 설정 | 서버의 앱 소유권 검증 대상(백엔드 문서 C2, env `KAKAO_APP_ID`) |
| Android 플랫폼 등록 | 패키지명 `com.redoceanmap.app` + **키 해시** | 디버그·릴리스 키 해시를 **둘 다** 등록 |
| iOS 플랫폼 등록 | 번들 ID `com.redoceanmap.app` | |
| 동의 항목 | 닉네임·프로필 사진·이메일(선택) | 이메일은 **선택 동의** — 없어도 로그인은 성공해야 한다(백엔드 C3) |
| 카카오싱크 약관 태그 | `age` · `terms` · `privacy` · `marketing` | 이미 서버가 쓰는 태그명(백엔드 C8) — 콘솔 등록값이 이와 같아야 한다 |

**키 해시 산출 명령** (등록 누락이 안드로이드 로그인 실패의 1순위 원인이다):

```bash
# 디버그 키스토어 (개발용)
keytool -exportcert -alias androiddebugkey -keystore ~/.android/debug.keystore \
  -storepass android -keypass android | openssl sha1 -binary | openssl base64
```

> 릴리스 빌드는 릴리스 키스토어로 같은 명령을 돌려 **별도 등록**한다. Play 앱 서명을 쓰면
> Play Console이 재서명하므로 **Play Console의 SHA-1을 base64로 변환한 값**도 등록해야 한다.

### P2. 앱이 붙을 오리진은 `api.` 가 아니라 `auth.` 다

토큰 발급은 개인키를 가진 auth 프로세스(`auth_main.py`, :9000)만 할 수 있다. 현재 `api.dart`의
`apiBase = https://api.redoceanmap.com` 하나로는 로그인 엔드포인트에 닿지 않는다.

> **권고:** `authBase = 'https://auth.redoceanmap.com'` 상수를 별도로 둔다.
> 두 오리진의 실제 라우팅(Cloudflare 터널) 확인이 필요하다 — **연결 확인 전에는 로그인 화면을
> 붙이지 않는다.** 확인 명령은 6절.

### P3. 로그인 상태 관리 방식

현재 앱에는 상태 관리 패키지가 없다(`StatelessWidget` + `Future` 직접 호출). 로그인 상태를 위해
새 패키지를 들이지 않는다.

> **권고:** 토큰을 들고 있는 얇은 싱글턴(`lib/auth.dart`) + `main.dart`의 부팅 시 1회 복원으로 끝낸다.
> Riverpod·Bloc 등 상태 관리 패키지 도입은 **이 티켓 범위 밖**이다.

### P4. 약관 동의 화면 (백엔드 C8 결정에 종속)

카카오싱크 필수 3종 동의가 콘솔에 등록되어 있으면 즉시 가입되고 앱 화면이 필요 없다.
등록되지 않았거나 사용자가 일부만 동의하면 서버가 `consent_token`을 돌려주므로
**앱 내 동의 화면 1개**가 필요하다. — 콘솔 등록 상태 확인 후 결정.

---

## 4. 확정 설계

### 4.1 추가할 의존성

```yaml
dependencies:
  kakao_flutter_sdk_user: ^2.0.0+1   # 로그인만 — kakao_flutter_sdk 전체 번들을 넣지 않는다
  flutter_secure_storage: ^10.3.1    # 리프레시 토큰 보관 (Keychain / EncryptedSharedPreferences)
```

(2026-08-03 `flutter pub add`로 실제 설치된 버전이다. 의존성 57개가 함께 들어왔다.)
`pubspec.lock`을 **함께 커밋**한다.
`kakao_flutter_sdk` 전체가 아니라 `_user` 모듈만 넣는다(친구·메시지 API는 명세 9절 Non-goal).

### 4.2 네이티브 설정 — ✅ 배선 완료 (2026-08-03)

**앱 키를 저장소에 남기지 않기 위해, 키를 적는 곳은 git 제외 파일 2개 + 실행 인자 1개뿐이다.**

| 플랫폼 | 키를 적는 곳 (git 제외) | 흘러가는 경로 |
| --- | --- | --- |
| Android | `android/local.properties` → `kakao.nativeAppKey=<키>` | `build.gradle.kts`가 읽어 `manifestPlaceholders`로 주입 → 매니페스트의 `android:scheme="kakao${kakaoNativeAppKey}"` |
| iOS | `ios/Flutter/Secrets.xcconfig` → `KAKAO_NATIVE_APP_KEY=<키>` | `Debug/Release.xcconfig`가 `#include?`로 읽음 → `Info.plist`의 `kakao$(KAKAO_NATIVE_APP_KEY)` |
| Dart | 실행 인자 `--dart-define=KAKAO_NATIVE_APP_KEY=<키>` | `String.fromEnvironment` → `KakaoSdk.init` |

- 리다이렉트 수신 액티비티는 `com.kakao.sdk.flutter.auth.AuthCodeHandlerActivity`,
  리다이렉트 URI는 `kakao<키>://oauth`다(SDK 2.0 실측 — `KakaoSdk.redirectUri`).
- **`<queries>`는 앱 매니페스트에 적지 않는다.** 카카오톡 패키지 가시성은 SDK 플러그인
  매니페스트가 이미 선언하고 병합된다(`kakao_flutter_sdk_common`의 AndroidManifest 실측).
- iOS `LSApplicationQueriesSchemes`의 `kakaokompassauth`는 앱 매니페스트에 필요하다 —
  누락 시 카카오톡 설치 여부 판별이 실패해 계정 로그인으로만 빠진다.

검증(2026-08-03): `flutter build apk --debug` 성공 + 병합 매니페스트에
`android:scheme="kakao"`·`android:host="oauth"`와 `com.kakao.talk` queries가 들어간 것을 확인했다
(키 미입력 상태라 스킴이 `kakao`로 끝나 있다 — 키를 넣으면 `kakao<키>`가 된다).

### 4.3 로그인 흐름

```
main()  →  KakaoSdk.init(nativeAppKey: …)         # 앱 시작 시 1회
   │
   │  [로그인 버튼]
   ▼
isKakaoTalkInstalled() ? loginWithKakaoTalk() : loginWithKakaoAccount()
   │      → OAuthToken 획득.  ★ me() 호출 없음 ★
   ▼
POST {authBase}/auth/mobile/kakao   body { accessToken, deviceId }
   │
   ├─ 200  { accessToken, refreshToken, … }
   │        → refreshToken을 flutter_secure_storage에 저장
   │        → accessToken은 메모리에만 (앱 재시작 시 refresh로 복원)
   │        → 카카오 OAuthToken 폐기
   │
   ├─ 409/consent_required (백엔드 C8)
   │        → 앱 내 동의 화면 → POST /auth/mobile/consent
   │
   └─ 401   → 로그인 실패 화면. 실패 사유를 세분해 노출하지 않는다(명세 7절)
```

`deviceId`는 기기 식별을 위한 **앱이 생성한 UUID**를 secure storage에 영속한다.
광고 식별자(IDFA/AAID)나 하드웨어 식별자를 쓰지 않는다.

### 4.4 저장 규칙 (명세 3.3 — 모바일)

| 값 | 저장 위치 | 이유 |
| --- | --- | --- |
| 리프레시 토큰 | `flutter_secure_storage` | Keychain / EncryptedSharedPreferences |
| `deviceId` | `flutter_secure_storage` | 재설치 시 새로 발급되는 것이 정상 |
| 액세스 토큰 | **메모리만** | 30분 수명 — 디스크에 남길 이유가 없다 |
| 카카오 토큰 | **어디에도 저장하지 않음** | 명세 2.4 |

`SharedPreferences`에 토큰을 넣지 않는다(평문 저장).

### 4.5 `api.dart` 변경

- `authBase` 상수 추가(P2).
- 인증이 필요한 요청에 `Authorization: Bearer <accessToken>` 헤더를 붙인다.
  쿠키는 쓰지 않는다(모바일은 헤더 전용 — 명세 3.3).
- **401 처리:** `POST {authBase}/auth/mobile/refresh` 1회 시도 → 성공하면 원 요청 1회 재시도,
  실패하면 저장소를 비우고 로그인 화면으로. **재시도는 1회로 고정**한다(무한 루프 방지).
- 응답 필드명은 백엔드 그대로 둔다(기존 `api.dart` 규칙 유지).

### 4.6 로그아웃

`POST {authBase}/auth/mobile/logout` → secure storage 삭제 → 메모리 토큰 삭제.
카카오 SDK 로그아웃(`UserApi.instance.logout()`)은 **선택**이다 — 자체 세션과 무관하며,
호출하면 다음 로그인 시 카카오톡 계정 선택이 다시 뜬다. 기본은 호출하지 않는다.

---

## 5. 파일 배치

```
flutter/app/lib/
├── auth.dart        # ✅ 구현됨 — Session(보관·복원) + AuthPage(로그인 화면) + authBase
├── main.dart        # ✅ 수정됨 — KakaoSdk.init + 부팅 시 세션 복원 → 홈/인트로 분기
├── intro_page.dart  # ✅ 수정됨 — 최대 10초 재생 후(또는 건너뛰기) AuthPage로
├── api.dart         # ✅ 최소 수정 — `_throwFrom` → `throwFrom`(auth.dart가 오류 매핑 재사용)
│                    #    미구현: Bearer 헤더 · 401 자동 갱신(4.5)
└── consent_page.dart# ✅ 구현됨(2026-08-03) — 필수 3종(age·terms·privacy)+마케팅 선택 →
                     #    POST /auth/mobile/consent. 실기기 검증은 아직(맥에서 flutter analyze/run)
```

기존 파일 수정은 **위 4.5·4.2에 해당하는 줄만** 건드린다(주변 코드를 정리하지 않는다).
`dart format`은 새 파일에만 건다 — 저장소의 기존 파일은 구 포맷 스타일이라 전체를 다시 들여쓴다.

---

## 6. 작업 순서 — 각 단계의 검증 명령

| # | 단계 | 검증 |
| --- | --- | --- |
| 0 | 백엔드 C1~C9 결정 + P1 콘솔 등록 | 콘솔에 키 해시·번들 ID·동의 항목이 보이면 통과 |
| 1 | 오리진 연결 확인(P2) | `curl -i https://auth.redoceanmap.com/auth/myself` → 200 |
| 2 | 의존성 추가 | `flutter pub get && flutter analyze` |
| 3 | 네이티브 설정(4.2) | `flutter run` 후 `isKakaoTalkInstalled()` 결과를 로그로 확인 — 카카오톡 설치 기기에서 **true** |
| 4 | 로그인 흐름(4.3) | 실기기에서 로그인 → 서버가 200 + 자체 JWT 반환 |
| 5 | 저장·복원(4.4) | 앱 강제 종료 후 재실행 → 재로그인 없이 화면 진입 |
| 6 | `api.dart` 인증 헤더·401 재시도(4.5) | `askChat`이 401 없이 응답 |
| 7 | 로그아웃(4.6) | 로그아웃 후 `askChat` → 401 |

실기기 연결·`flutter doctor` 문제는 [[flutter/_docs/flutter-harness|flutter harness]]의 5절 표를 먼저 본다.

**실행 명령**(앱 키 주입 누락이 흔한 실패 원인이다):

```bash
cd /Users/jangminseok/Project/com.redoceanmap/flutter/app
flutter run -d <device-id> --dart-define=KAKAO_NATIVE_APP_KEY=<네이티브 앱 키>
```

---

## 7. 완료 조건 — 클라이언트 몫

- [ ] **`UserApi.instance.me()` 호출이 존재하지 않는다**
      → `grep -rn "\.me()" flutter/app/lib` 결과가 **비어 있어야 한다**
- [ ] 서버로 보내는 body에 프로필 필드가 없다(`accessToken`·`deviceId`만)
      → `grep -rn "nickname\|profileImage" flutter/app/lib` 결과 없음
- [ ] 카카오 토큰이 어디에도 저장되지 않는다(secure storage 키 목록에 없음)
- [ ] 앱 키가 소스에 하드코딩되어 있지 않다
      → `grep -rn "kakao[0-9a-f]\{20,\}" flutter/app/lib` 결과 없음
- [ ] 앱 재시작 후 재로그인 없이 세션이 복원된다(리프레시 30일)
- [ ] 액세스 토큰 만료 시 자동 갱신되고, 갱신 실패 시 **1회만** 재시도 후 로그인 화면으로 간다
- [ ] 로그인 실패 메시지가 원인을 세분해 노출하지 않는다
- [ ] 카카오톡 미설치 기기에서 계정 로그인(웹뷰)으로 정상 폴백된다
- [ ] `flutter analyze` 무경고

---

## 8. 범위 밖

- 카카오 외 소셜 로그인 버튼 (구글·애플) — 만들지 않는다
- 카카오 API 연동(친구 목록·메시지 전송) — `kakao_flutter_sdk_user`만 넣는 이유
- 회원 탈퇴 / 연결 끊기 — 별도 티켓
- 상태 관리 패키지 도입(P3) · 웹(www) 로그인 UI 변경
