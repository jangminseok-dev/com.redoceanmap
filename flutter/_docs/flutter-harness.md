# Flutter 하네스 — 실제 단말 테스트 환경

> 원전: 『Must Have 코드팩토리의 플러터 프로그래밍(2판)』 5.3 "실제 단말 테스트 환경 구축".
> 원문은 Flutter 3.x 초기 기준이라 **경로·버전·필수 절차가 현재와 다르다.**
> 이 문서는 2026-07-31 이 맥에서 **직접 실행해 확인한 값**으로 다시 쓴 것이다.
> 각 절은 "따라 하면 되는 절차"가 아니라 **검증 명령으로 성공을 확정하는 절차**로 적었다.

관련: [[_docs/harness|harness]] · [[CLAUDE|루트 CLAUDE]]

---

## 1. 실측 환경 (2026-07-31, `flutter doctor -v` 및 SDK 파일 직접 확인)

| 구성 | 확인된 버전 | 확인 방법 |
| --- | --- | --- |
| Flutter | **3.44.8** (stable) · Dart **3.12.2** · DevTools 2.57.0 | `flutter --version` |
| Flutter SDK 경로 | `/Users/jangminseok/VScode/flutter` | `which flutter` |
| Android SDK | `~/Library/Android/sdk` · platform **android-36.1** | `flutter doctor -v` |
| Build-Tools | 36.0.0 · 36.1.0 · **37.0.0** | `ls $ANDROID_HOME/build-tools` |
| Platform-Tools(adb) | **37.0.0** (`adb 1.0.41`) — 저장소에 37.0.1 존재 | `adb version` |
| NDK | **28.2.13676358** | `ls $ANDROID_HOME/ndk` |
| JDK | **OpenJDK 21** (Android Studio 번들 JBR) | `flutter doctor -v` |
| Android Studio | **2026.1** (build AI-261.23567.138) | `Info.plist` |
| Xcode | **26.6** (build 17F113) | `flutter doctor -v` |
| CocoaPods | **1.16.2** (Flutter 권장 버전과 동일) | `flutter doctor -v` |
| 호스트 | macOS **26.5.1** · darwin-arm64 (Apple Silicon) | `flutter doctor -v` |

**Flutter 3.44.8이 새 앱에 넣는 Android 기본값** (`flutter_tools`의 `FlutterExtension.kt`·`gradle_utils.dart` 실측):

| 항목 | 값 |
| --- | --- |
| `minSdk` | **24** (Android 7.0) |
| `compileSdk` / `targetSdk` | **36** (Android 16) |
| `ndkVersion` | 28.2.13676358 |
| Gradle | **9.1.0** |
| Android Gradle Plugin | **9.0.1** |
| Kotlin Gradle Plugin | **2.3.20** |
| Java source/target | **17** (툴체인 JDK는 21) |
| iOS 배포 타깃 | **13.0** |

---

## 2. 원문에서 바뀐 것 — 그대로 따르면 안 되는 부분

| 원문(책) | 2026-07-31 현재 | 근거 |
| --- | --- | --- |
| "USB 디버깅은 Android 4.1 / API 16 이상" | Flutter 3.44의 **`minSdk = 24`** (Android 7.0). API 16~23 기기는 앱 자체가 설치되지 않는다 | `FlutterExtension.kt:26` |
| "안드로이드 스튜디오에서 **Google USB Driver**를 설치" | **Windows 전용이다. macOS에는 존재하지도 않는다** — macOS SDK Manager 목록(`sdkmanager --list`)에 `extras;google;usb_driver` 항목 자체가 없다. 맥/리눅스는 케이블만 꽂으면 된다 | `sdkmanager --list` 실측 |
| "무선 디버깅은 참고 링크로 대체" | **Android 11(API 30)+ 기본 기능.** 케이블보다 이쪽이 기본 경로다. adb 37.0.0 + Android 17에서 **adb Wi-Fi 2.0** — 한 번 페어링하면 신뢰 네트워크 접속 시 자동 재연결 | developer.android.com/tools/adb |
| 개발자 옵션 경로(Android 7~9 기준 3분기) | Android 12+ 단일 경로로 수렴. 삼성 One UI는 [소프트웨어 정보] 한 단계가 더 있다 | 아래 3.1 |
| iOS: `sudo gem install cocoapods` | **시스템 Ruby에 `sudo gem`을 쓰지 않는다.** Homebrew로 설치한다 | 아래 4.2 |
| iOS: `gem uninstall ffi && gem install ffi -- --enable-libffi-alloc` | **불필요.** Apple Silicon 네이티브 gem이 배포된 뒤로 사라진 워크어라운드다 | 아래 4.2 |
| iOS 14+ 디버그 에러 → "Xcode에서 Release로 바꿔라" | **바꾸지 않는다.** 이 메시지는 "홈 화면 아이콘 탭으로는 디버그 빌드를 못 켠다"는 뜻일 뿐이고, `flutter run` / IDE 실행은 정상이다. Release로 바꾸면 핫 리로드·DevTools를 잃는다 | 아래 4.4 |
| 배포 시 타깃 API | **2026-08-31부터 Google Play 신규 등록·업데이트는 API 36 이상 필수** (연장 신청 시 2026-11-01). Flutter 기본값 36이 이미 이 조건을 만족한다 | developer.android.com/google/play/requirements/target-sdk |

---

## 3. 안드로이드 실제 기기

### 3.1 개발자 옵션 활성화 (케이블·무선 공통)

Android 12 이상 기준이다(현재 유통 기기는 사실상 전부 해당). 제조사별로 한 단계만 다르다.

| 기기 | 빌드 번호 위치 |
| --- | --- |
| Pixel / AOSP 계열 | [설정] → [휴대전화 정보] → **[빌드 번호]** 7번 탭 |
| 삼성 One UI | [설정] → [휴대전화 정보] → **[소프트웨어 정보]** → **[빌드 번호]** 7번 탭 |

탭 도중 화면 잠금(PIN·패턴)이 걸려 있으면 인증을 요구한다. 완료되면 "개발자가 되셨습니다" 토스트가 뜬다.

이어서 디버깅을 켠다.

| 기기 | 개발자 옵션 위치 | 켜야 할 항목 |
| --- | --- | --- |
| Pixel / AOSP | [설정] → [시스템] → [개발자 옵션] | **USB 디버깅** / **무선 디버깅** |
| 삼성 One UI | [설정] → [개발자 옵션] (최상위) | 동일 |

> 케이블로 붙일 거면 `USB 디버깅`, 와이파이로 붙일 거면 `무선 디버깅`이다. 둘 다 켜도 무방하다.

### 3.2 데이터 케이블로 연결 (기기 ↔ 개발 맥을 USB 케이블로 직결)

**충전 전용 케이블은 데이터 선이 없어 인식되지 않는다.** 기기 동봉 케이블이나 데이터 지원 케이블을 쓴다.

1. 케이블로 기기와 맥을 연결한다.
2. 기기에 **"USB 디버깅을 허용하시겠습니까?"** 대화상자가 뜨면 **[이 컴퓨터에서 항상 허용]** 체크 후 [허용].
   - 대화상자가 안 뜨면 기기의 USB 사용 모드를 **[파일 전송 / MTP]** 로 바꾼다(충전 전용이면 안 뜬다).
3. macOS에서는 **드라이버 설치가 필요 없다**(2절 참조).

**검증 — 이 두 명령이 통과해야 성공이다.**

```bash
# 1) adb가 기기를 잡았는가 — 'device' 여야 한다
$ANDROID_HOME/platform-tools/adb devices -l
# unauthorized  → 기기의 허용 대화상자를 아직 안 눌렀다
# offline       → 케이블 재연결 또는 adb kill-server && adb start-server
# (빈 목록)      → 충전 전용 케이블이거나 USB 디버깅 미활성

# 2) Flutter가 기기를 인식했는가
flutter devices
```

`ANDROID_HOME`이 없으면 `~/Library/Android/sdk`가 이 맥의 경로다. `adb`는 PATH에 없으므로
자주 쓸 거면 셸 프로필에 다음을 넣는다.

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$PATH:$ANDROID_HOME/platform-tools"
```

### 3.3 와이파이 무선 디버깅 (Android 11 / API 30 이상)

케이블 없이 붙는다. **맥과 기기가 같은 와이파이(같은 서브넷)에 있어야 한다.**
회사·학교 AP의 클라이언트 격리(AP isolation)가 켜져 있으면 실패한다.

1. 기기: [개발자 옵션] → **[무선 디버깅]** 켜기 → 네트워크 사용 허용
   (자주 쓰는 망이면 "이 네트워크에서 항상 허용" 체크).
2. 기기: [무선 디버깅] → **[페어링 코드로 기기 페어링]** 탭.
   → **6자리 페어링 코드**와 **IP:포트**가 표시된다 (이 포트는 페어링 전용 1회용이다).
3. 맥 터미널:

```bash
adb pair 192.168.0.10:37411   # 화면에 뜬 IP:포트 (페어링용)
# Enter pairing code: 123456
# → Successfully paired to ...

adb connect 192.168.0.10:5555 # [무선 디버깅] 첫 화면의 IP:포트 (연결용, 위와 다르다)
adb devices                    # 목록에 IP:포트 형태로 뜨면 성공
flutter devices
```

**두 포트를 헷갈리는 것이 이 절차의 유일한 함정이다.** `adb pair`에 쓰는 포트는
"페어링 코드로 기기 페어링" 화면의 것이고, `adb connect`에 쓰는 포트는 [무선 디버깅] 첫 화면의 것이다.

Android Studio 2026.1을 쓴다면 기기 선택 드롭다운 → **[Pair Devices Using Wi-Fi]** 에서
QR 코드로 2~3번을 대체할 수 있다.

> **adb Wi-Fi 2.0** — adb 37.0.0(이 맥에 설치됨) + Android 17 기기 조합에서는 한 번 페어링하면
> 이후 해당 네트워크에 접속할 때 **자동으로 다시 연결**된다. `adb connect`를 매번 칠 필요가 없다.
> 지원 여부 확인: `adb mdns track-services --proto-text` 출력에 `mdns_service_version: "2.0"`.
> 페어링 해제는 기기의 [무선 디버깅] → [페어링된 기기] → 해당 워크스테이션 → [삭제].

### 3.4 실행

```bash
flutter devices                      # 대상 id 확인
flutter run -d <device-id>           # 디버그 실행 (핫 리로드 r / 핫 리스타트 R / 종료 q)
flutter run -d <device-id> --release # 릴리스 성능 확인용
```

Android Studio·VS Code에서는 우측 상단(또는 하단 상태바) 기기 선택기에서 고르고 실행하면 된다.

---

## 4. 아이폰 실제 기기 (macOS 필수)

이 맥은 Xcode 26.6 · CocoaPods 1.16.2로 이미 조건을 만족한다(`flutter doctor` No issues found).
참고로 Flutter 3.44.8의 Xcode 최소 요구는 15, 권장은 16 이상이다.

### 4.1 기기 준비

1. 케이블로 아이폰을 맥에 연결하고, 기기에 뜨는 **[신뢰]** 를 누른 뒤 암호를 입력한다.
2. **iOS 16 이상**: [설정] → **[개인정보 보호 및 보안]** → 맨 아래 **[개발자 모드]** 켜기 → 재부팅 → 잠금 해제 후 **[켜기]** 확인.
   - **[개발자 모드] 항목이 안 보이면** 아직 이 맥에서 개발용 앱을 한 번도 설치·실행하지 않은 것이다.
     `flutter run`을 한 번 시도하면 항목이 나타난다.

### 4.2 CocoaPods

**책의 `sudo gem install cocoapods`를 그대로 실행하지 않는다.** 최신 macOS의 시스템 Ruby에
`sudo gem`으로 설치하면 권한 문제와 다른 gem 환경과의 충돌을 일으킨다. Homebrew를 쓴다.

```bash
brew install cocoapods     # 이미 설치돼 있으면 brew upgrade cocoapods
pod --version              # Flutter 3.44 권장 = 1.16.2, 최소 = 1.10.0
```

책의 `sudo gem uninstall ffi && sudo gem install ffi -- --enable-libffi-alloc` 는
**실행하지 않는다.** Apple Silicon 네이티브 ffi gem이 나온 뒤로 필요 없어진 워크어라운드이며,
지금 실행하면 오히려 gem 환경을 망가뜨린다.

### 4.3 서명(Signing) 설정 — 프로젝트당 1회

무료 Apple ID로도 실기기 실행이 된다(7일마다 재설치 필요, 앱 3개 제한).

1. `open ios/Runner.xcworkspace` — **`.xcodeproj`가 아니라 `.xcworkspace`** 를 연다.
2. 좌측 네비게이터 최상단 **[Runner]** → TARGETS의 **[Runner]** → **[Signing & Capabilities]** 탭.
3. **Bundle Identifier**를 전 세계에서 유일한 값으로 바꾼다 (`com.<본인>.<앱이름>` 형태).
4. **[Automatically manage signing]** 체크 → **Team**에서 Apple 계정 선택
   (없으면 [Add an Account…]로 로그인하면 "(Personal Team)"이 생긴다).

> Bundle ID는 애초에 프로젝트 생성 시에 정하는 편이 낫다:
> `flutter create --org com.본인 <프로젝트명>` — Android `applicationId`와 iOS Bundle ID가 한 번에 잡힌다.

첫 실행 시 기기에서 **[설정] → [일반] → [VPN 및 기기 관리]** → 본인 개발자 앱 → **[신뢰]** 를 눌러야 한다.

### 4.4 실행 — "Release로 바꾸라"는 조언은 따르지 않는다

```bash
flutter run -d <device-id>
```

책이 인용한 경고(*"In iOS 14+, debug mode Flutter apps can only be launched from Flutter tooling,
IDEs with Flutter plugins or from Xcode"*)는 **에러가 아니라 정상 동작 설명**이다.
의미는 "홈 화면 아이콘을 탭해서는 디버그 빌드를 실행할 수 없다"이며, `flutter run`이나 IDE 실행 버튼으로는
정상적으로 뜬다. 이때 Xcode 스킴을 Release로 바꾸면 **핫 리로드·DevTools·디버거를 전부 잃는다.**
홈 화면 아이콘으로 켜고 싶을 때만 `flutter run --profile` 또는 `--release`를 쓴다.

---

## 5. 트러블슈팅 — 증상 → 확인 순서

| 증상 | 먼저 볼 것 |
| --- | --- |
| `flutter devices`에 안 보임 | ① `adb devices`부터 확인 — adb가 못 보면 Flutter도 못 본다 ② 충전 전용 케이블 ③ USB 모드를 [파일 전송]으로 |
| `adb devices`가 `unauthorized` | 기기의 USB 디버깅 허용 대화상자 미승인. 안 뜨면 [개발자 옵션] → [USB 디버깅 승인 취소] 후 재연결 |
| `adb devices`가 `offline` | `adb kill-server && adb start-server` → 재연결 |
| `adb pair` 실패 / 코드 거부 | 페어링용 포트와 연결용 포트를 바꿔 넣었을 가능성이 가장 크다(3.3 참조). 페어링 화면을 닫으면 포트가 무효화된다 |
| 무선 연결이 계속 끊김 | AP의 클라이언트 격리, 또는 맥·기기가 서로 다른 대역/게스트망. adb Wi-Fi 2.0 미지원 기기는 재접속마다 `adb connect` 필요 |
| `INSTALL_FAILED_OLDER_SDK` | 기기가 Android 7.0(API 24) 미만. Flutter 3.44에서는 지원 불가 |
| Gradle/JDK 관련 빌드 실패 | `flutter doctor -v`의 Java 경로 확인. Android Studio 번들 JBR(21) 사용이 기본이며, 다르면 `flutter config --jdk-dir="<경로>"` |
| iOS: 기기에 "신뢰할 수 없는 개발자" | [설정] → [일반] → [VPN 및 기기 관리]에서 [신뢰] |
| iOS: 서명 오류 | Bundle ID 중복 또는 Team 미선택(4.3). 무료 계정은 7일마다 만료되므로 재실행 |
| 원인 불명 | `flutter clean && flutter pub get` 후 재시도. 그래도 안 되면 `flutter doctor -v` 전문을 먼저 읽는다 |

**환경 자체 검증은 항상 여기서 시작한다.**

```bash
flutter doctor -v   # 기대: [✓] Flutter / Android toolchain / Xcode / Connected device
```

---

## 6. 참고 문서 (2026-07-31 기준 유효 URL)

- Flutter Android 개발 환경 — https://docs.flutter.dev/platform-integration/android/setup
- Flutter macOS에서 Android 앱 시작 — https://docs.flutter.dev/get-started/install/macos/mobile-android
- adb / 무선 디버깅 — https://developer.android.com/tools/adb
- 실기기 실행(Android Studio) — https://developer.android.com/studio/run/device
- Google Play 타깃 API 요구사항 — https://developer.android.com/google/play/requirements/target-sdk

> 책이 안내한 `https://docs.flutter.dev/get-started/install/windows#android-setup` 은
> **윈도우 기준**이며 현재 문서 구조와도 맞지 않는다. 이 저장소의 개발 기기는 맥이므로 위 URL을 쓴다.
