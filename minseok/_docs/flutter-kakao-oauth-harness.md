# 인증 시스템 구현 명세 — 백엔드 (Kakao OAuth + 자체 JWT)

> 원 명세는 사용자가 전달한 "인증 시스템 구현 명세"다. 이 문서는 그 명세를 **이 저장소의 실제 코드와
> 대조해** 백엔드(minseok) 몫으로 확정한 작업 명세다. 모바일 클라이언트 몫은
> [[flutter/_docs/flutter-kakao-oauth-harness|flutter kakao oauth harness]]에 있다.
>
> **진행 상황(2026-08-03):** `POST /auth/mobile/kakao` 슬라이스를 구현했다(8절).
> 3절 충돌 중 **C2·C3·C7·C8은 아래 권고대로 확정해 반영**했고,
> **C1·C4·C5·C6은 이 엔드포인트 범위 밖이라 손대지 않았다** — 결정은 여전히 열려 있다.

관련: [[minseok/_docs/CLAUDE|minseok CLAUDE]] · [[minseok/apps/auth/_docs/CLAUDE|auth CLAUDE]] · [[CLAUDE|루트 CLAUDE]]

---

## 1. 저장소 현황 실측 (2026-08-03, 파일 직접 확인)

명세가 "새로 만든다"고 가정한 것들 중 **이미 존재하는 것**이다.

| 명세 항목 | 저장소 현황 | 근거 |
| --- | --- | --- |
| 카카오 로그인 | **웹은 이미 동작 중** — 서버 주도 Authorization Code(BFF). 서버가 `state` 생성·쿠키 검증·코드 교환·프로필 조회까지 수행 | `apps/auth/adapter/inbound/api/v1/social_router.py:75,94` |
| 카카오 프로필 조회 | `kapi.kakao.com/v2/user/me` + `/v2/user/service_terms` 서버 호출 구현됨 | `apps/auth/adapter/outbound/gateways/social_oauth_gateway.py:65,97` |
| 자체 JWT | RS256. **발급은 auth 프로세스(`auth_main.py`, :9000)만** — 개인키 `.env.auth` 경계 | `core/config.py:35`, `auth_main.py` |
| JWT 검증 | 전 라우터 공용 의존성 `get_current_user_id` (쿠키 우선 → Bearer 폴백) + 매 요청 users 상태 조회 | `core/security.py:26` |
| 리프레시 토큰 | Redis 저장 + **회전 구현됨**(refresh 시 기존 토큰 삭제) | `auth_interactor.py:90`, `refresh_token_redis_repository.py` |
| 만료 | 액세스 **60분** · 리프레시 **14일** (플랫폼 구분 없음) | `auth_interactor.py:15` |
| users 테이블 | `email` **UNIQUE NOT NULL**, `password_hash` NOT NULL, `terms_agreed_at`, `marketing_agreed`, `suspended_at`, `deleted_at` | `apps/auth/adapter/outbound/orm/user_orm.py` |
| Redis | 단일 클라이언트 · **db 0 고정** · 비밀번호 없음 · `127.0.0.1:6379` 노출 · `appendonly yes` 이미 적용 | `core/redis.py:17`, `core/config.py:56`, `docker-compose.yaml:61` |
| 소셜 계정 식별 | **이메일 기준 연동**(`find_by_email`) — 카카오 이메일 미동의 시 로그인 거부 | `social_interactor.py:88`, `social_oauth_gateway.py:87` |
| 약관 동의 | 신규 유저는 동의 전까지 **생성하지 않는다.** 카카오싱크 필수 3종(`age`·`terms`·`privacy`) 동의면 즉시 가입, 아니면 `consent_token` 발급 후 자체 동의 화면 | `social_interactor.py:90,101` |
| compose 파일명 | `docker-compose.yaml` (명세의 `.yml` 아님) | 저장소 루트 |

---

## 2. 명세와 충돌하지 않는 부분 (그대로 채택)

- **2.1 클라이언트가 보낸 프로필을 신뢰하지 않는다** — 현행 웹이 이미 이 원칙을 지킨다.
- **2.2 클라이언트에서 `me()`를 호출하지 않는다** — 모바일도 동일. 플러터 문서에서 강제한다.
- **2.4 카카오 토큰을 저장하지 않는다** — 현행도 저장하지 않는다(요청 스코프 안에서 소멸).
- **7절 보안 요구사항** — 카카오 토큰은 POST body, HTTPS, 키는 env, 로그 마스킹.
- **8절 "카카오 API 무응답 시 기존 JWT 세션은 정상 동작"** — 현 구조상 이미 성립한다.
  검증이 로컬 공개키 서명 확인이라 카카오 호출이 없다(`core/security.py:49`).

---

## 3. 명세 ↔ 저장소 충돌 — 착수 전 결정 필요 ★

각 항목은 **명세대로 하면 무엇이 깨지는지**와 권고를 함께 적는다. 결정 전에는 구현하지 않는다.

### C1. 웹까지 명세대로 바꾸면 현행 BFF보다 보안이 후퇴한다

명세 5절은 클라이언트가 `accessToken`을 body로 보내는 방식이다. 모바일은 SDK 특성상 이 방식이
유일하지만, **웹에 그대로 적용하려면 브라우저 JS가 카카오 액세스 토큰을 쥐어야 한다.** 현행 웹은
서버가 코드를 교환해 카카오 토큰이 브라우저에 내려오지 않는다 — 명세 2.1 원칙을 더 강하게 지킨다.

> **권고:** 웹은 **현행 BFF 흐름을 유지**하고 경로만 명세의 이름 규칙에 맞춘다
> (`/auth/social/kakao/start`·`/callback` 유지 + `/auth/web/refresh`·`/auth/web/logout` 신설).
> `POST /auth/web/kakao`(토큰 수령형)는 **만들지 않는다.**
> — 명세대로 웹도 토큰 수령형으로 통일할지 **사용자 결정 필요.**

### C2. `app_id`는 `/v2/user/me` 응답에 없다

명세 5절은 "`/v2/user/me` 호출 → 응답의 `app_id` 검증"이라고 적었으나, 카카오 문서 기준 `/v2/user/me`가
주는 필드는 `id`·`connected_at`·`kakao_account`·`properties`이며 **`app_id`는 없다.**
앱 소유권(`app_id`)은 `GET https://kapi.kakao.com/v1/user/access_token_info`가 반환한다
(`id`·`expires_in`·**`app_id`**). 명세에서 가장 중요하다고 지목한 검증이므로, 그대로 구현하면
검증이 **조용히 누락**된다.

**착수 전 실측 명령**(실 토큰으로 1회 확인하고 결과를 이 표에 남긴다):

```bash
curl -s -H "Authorization: Bearer $KAKAO_ACCESS_TOKEN" \
  https://kapi.kakao.com/v1/user/access_token_info   # app_id 존재 확인
curl -s -H "Authorization: Bearer $KAKAO_ACCESS_TOKEN" \
  https://kapi.kakao.com/v2/user/me                  # app_id 부재 확인
```

> **권고:** 검증 순서를 **① `access_token_info`로 `app_id`+`id` 확인 → ② 신규 가입일 때만
> `/v2/user/me`로 프로필 보강**으로 바꾼다(명세 2.3의 의도는 그대로 지킨다).
> 비교 대상은 새 env `KAKAO_APP_ID` — 기존 REST 키 `KAKAO_CLIENT_ID`와 **다른 값**이다.

### C3. `users` 테이블을 명세 6절대로 만들면 기존 기능이 깨진다

명세 6절 표(`kakao_id`·`nickname`·`profile_image`·…)는 신규 테이블 정의다. 현행 `users`에는
이메일/비밀번호 로그인·RBAC(`user_roles`)·admin·`suspended_at`/`deleted_at` 제재가 전부 매달려 있다.
갈아엎으면 auth 밖의 앱까지 연쇄로 깨진다.

> **권고:** 테이블을 새로 만들지 말고 **컬럼만 더한다.**
> - `kakao_id BIGINT NULL UNIQUE` 추가 → 카카오 로그인은 이 컬럼으로 조회(이메일 연동 폐기).
> - `email`을 **nullable**로 완화(명세 6절: 이메일은 동의 항목이라 없을 수 있다).
>   영향 범위 — `UserRepository.find_by_email`, `SessionResponse.email`, 이메일 로그인 경로의 None 처리.
>   UNIQUE 제약은 유지한다(Postgres는 NULL 중복을 허용한다).
> - `nickname`·`profile_image`는 **기존 `name` 컬럼으로 충당**한다(중복 컬럼을 만들지 않는다).
> - `last_login_at`은 명세 요구대로 추가.
>
> alembic 리비전 1개로 끝난다. "유저는 플랫폼과 무관하게 하나"라는 명세 6절 원칙은 그대로 성립한다.

### C4. `/api/mobile/*` · `/api/web/*` 네임스페이스가 저장소에 없다

명세 3.2와 완료 조건은 "요청 경로의 플랫폼과 토큰 클레임 일치"를 요구하지만, 현 API 경로는
`/market/*`·`/chat/*`·`/stock/*`처럼 **도메인별**이고 플랫폼 접두가 없다. 전면 도입하면 모든 라우터 +
www의 `/api/backend` rewrite + 플러터 `api.dart`가 함께 바뀐다.

> **권고(b안):** 경로 접두는 **auth 계열에만** 둔다(`/auth/mobile/*`·`/auth/web/*`).
> 공용 비즈니스 API는 두 플랫폼이 같은 데이터를 보므로 `platform` 클레임의 존재만 확인하고 통과시킨다.
> 교차 사용 차단이 실제로 의미 있는 지점(리프레시·로그아웃·세션 폐기)은 전부 auth 계열이다.
>
> **a안(명세 그대로):** `/api/{platform}/*` 전면 도입 — 비용이 크고 이 티켓 범위를 넘는다.
> — **a/b 사용자 결정 필요.** 완료 조건 3·4번 문구도 결정에 맞춰 다시 쓴다.

### C5. `platform` 검증 위치는 "미들웨어"가 아니라 기존 공용 의존성이다

명세 3.2는 미들웨어를 지목하지만, 이 저장소의 단일 인증 관문은 `core/security.py`의
`get_current_user_id`다. 미들웨어를 새로 두면 관문이 둘로 갈라진다.

> **권고:** `get_current_user_id`가 `platform` 클레임을 읽고, 플랫폼 고정이 필요한 라우터는
> `require_platform("mobile")` 가드(같은 파일, `require_permission`과 같은 팩토리 패턴)를 붙인다.
> 미들웨어는 만들지 않는다.
>
> **하위 호환 결정 필요:** `platform` 클레임이 없는 **기존 발급 토큰**의 처리.
> 권고는 "클레임 없으면 `web`으로 간주"하되, 배포 후 웹 리프레시 만료(7일)가 지나면 폴백을 제거.

### C6. Redis 비밀번호를 켜면 `REDIS_URL`을 쓰는 모든 곳이 함께 죽는다

명세 4.4의 `--requirepass`는 `core/redis.py`(리프레시 저장)와 `core/rate_limit.py`(로그인 한도),
그리고 backend·auth 두 컨테이너의 `REDIS_URL`에 **동시에** 반영해야 한다.

> **권고:** 같은 커밋에서 함께 바꾼다. `.env`에 `REDIS_PASSWORD` 추가 → `.env.example` 등록 →
> `docker-compose.yaml`의 두 서비스 `REDIS_URL`을 `redis://:${REDIS_PASSWORD}@redis:6379/0`으로.
> 메모리의 "약한 DB 비밀번호 교체 대기"와 같은 성격의 작업이다.
> `ports` 매핑 제거는 명세대로 수용한다(현재도 `127.0.0.1` 바인딩이라 LAN 노출은 없고, 디버깅은
> `docker exec … redis-cli`로 가능하다). `--databases 2`는 이후 db 2 이상을 못 쓰게 하지만
> 현재 사용처가 db 0뿐이라 문제없다.

### C7. 리프레시 토큰에 `jti`·Hash·denylist 개념이 없다

현행 리프레시 토큰은 JWT가 아니라 `secrets.token_urlsafe(48)` 랜덤 문자열이고, Redis에는
`auth:refresh:{token} → JSON` 한 벌 + 유저 역인덱스 set만 있다. 명세 4.2의
`{userId}:{jti}` Hash · `devices` Set · `denylist`는 **구조 변경**이다.

> **권고:** 랜덤 문자열을 **그대로 `jti`로 쓴다**(리프레시를 JWT로 바꾸지 않는다 — 불필요한 복잡도).
> 현행 역인덱스 set의 이름을 `mobile:devices:{userId}`로 맞추면 4.2 구조가 거의 그대로 나온다.
> **denylist는 새로 필요하다** — 현행은 "회전돼 삭제된 토큰"과 "존재한 적 없는 토큰"을 구분할 수 없어
> 명세 4.3의 재사용 탐지 → 전량 무효화가 불가능하다.

### C8. 모바일 신규 가입 시 약관 동의 증빙이 비어버린다

명세 5절은 "없으면 신규 가입"으로 끝나지만, 현행은 `terms_agreed_at` 없이 유저를 만들지 않는다
(`social_interactor.py:101`). 명세대로만 구현하면 법적 동의 증빙이 사라진다.

> **권고:** 기존 카카오싱크 경로를 재사용한다 — `_kakao_service_terms`로 필수 3종 동의를 확인해
> 충족하면 즉시 가입, 아니면 `consent_token`을 응답해 **앱 내 동의 화면**을 거치게 한다
> (`POST /auth/mobile/consent`). 웹의 2단계 구조와 동형이다.

### C9. 만료 정책 변경은 쿠키 상수와 짝을 맞춰야 한다

`cookie.py:19`의 `ACCESS_MAX_AGE`/`REFRESH_MAX_AGE`는 인터랙터 상수와 일치시키는 것이 규칙이다.
웹을 15분/7일로 바꾸면 두 파일을 함께 고친다. 기존 14일 세션은 다음 회전에서 자연히 7일로 수렴한다.

---

## 4. 확정 설계 (위 결정이 난 뒤 이 절대로 구현한다)

### 4.1 엔드포인트

| 경로 | 프로세스 | 비고 |
| --- | --- | --- |
| `POST /auth/mobile/kakao` | auth(:9000) | body `{ accessToken, deviceId }` · 신규 |
| `POST /auth/mobile/consent` | auth | C8 — 필수 약관 미동의 시에만 |
| `POST /auth/mobile/refresh` | auth | 리프레시를 body로 받고 body로 돌려준다(쿠키 아님) |
| `POST /auth/mobile/logout` | auth | 멱등 |
| `GET  /auth/mobile/myself` | auth | **라우터 컨벤션 필수** — 실기능 자기소개 |
| `POST /auth/web/refresh` · `/auth/web/logout` | auth | 기존 `/auth/refresh`·`/auth/logout` 경로 정리 |
| 기존 `/auth/social/kakao/start`·`/callback` | auth | **유지**(C1) |

**토큰 발급은 auth 프로세스에만 둔다.** backend(:8000)는 개인키가 없어 토큰을 만들 수 없다 —
이 경계를 넘지 않는다. 따라서 앱은 `auth.redoceanmap.com`에 붙는다(플러터 문서 4.1 참조).

**JSON 계약** — 앱(`flutter/app/lib/auth.dart`)이 이미 이 형태로 구현되어 있다. 서버는 이에 맞춘다.
기존 웹 `SessionResponse`(본문에 토큰 없음)와 달리 모바일은 **본문으로 토큰을 내린다**(쿠키 없음).

| 요청 | 본문 |
| --- | --- |
| `POST /auth/mobile/kakao` | `{ "accessToken": "<카카오 토큰>", "deviceId": "<앱 생성 난수>" }` |
| `POST /auth/mobile/refresh` | `{ "refreshToken": "…" }` |

응답(200): `{ "accessToken": "…", "refreshToken": "…" }` — 필드명은 camelCase로 고정한다
(기존 `/market`·`/chat` 응답과 같은 표기). 실패는 기존 규칙대로 `{"detail": "<한국어 메시지>"}`.

### 4.2 JWT 클레임

```
{ "sub": "<user_id>", "platform": "mobile" | "web", "jti": "<토큰 식별자>", "exp": … }
```

- 알고리즘은 RS256 리터럴 고정(현행 유지 — 알고리즘 혼동 공격 방지).
- 검증 순서: 서명 → `platform` → 기존 계정 상태 조회(`core/security.py`).

### 4.3 만료

| | Access | Refresh |
| --- | --- | --- |
| 모바일 | 30분 | 30일 |
| 웹 | 15분 | 7일 |

### 4.4 Redis

```
db 0 (웹)      web:refresh:{userId}:{jti}     Hash   { issuedAt, userAgent, ip }        TTL 7d
               web:denylist:{jti}             String "1"                                TTL 잔여 만료시간
db 1 (모바일)  mobile:refresh:{userId}:{jti}  Hash   { deviceId, issuedAt, userAgent }  TTL 30d
               mobile:devices:{userId}        Set    { jti, … }                         TTL 30d
               mobile:denylist:{jti}          String "1"                                TTL 잔여 만료시간
```

- 클라이언트를 **두 인스턴스**로 만든다(`core/redis.py`에 `get_redis_web()`/`get_redis_mobile()`).
  하나의 클라이언트에서 `SELECT`로 전환하지 않는다(커넥션 풀 오염).
- 논리 DB를 나눠도 **키 프리픽스를 유지**한다(덤프·마이그레이션 시 출처 식별).
- **재사용 탐지:** refresh 요청의 `jti`가 denylist에 있으면 탈취로 간주하고
  **그 플랫폼의 그 유저 토큰만** 전량 폐기한다. 다른 플랫폼 세션은 유지한다.
- `core/rate_limit.py`는 db 0을 계속 쓴다(세션 키가 아니므로 무방).

### 4.5 새로 추가할 환경변수

| 키 | 용도 |
| --- | --- |
| `KAKAO_APP_ID` | C2 — 앱 소유권 검증 대상값(REST 키와 다른 숫자 ID) |
| `REDIS_PASSWORD` | C6 |
| `REDIS_URL_MOBILE` | db 1 접속 문자열 |

각각 `.env` → **`.env.example` 등록** → `core/config.py` 상수 한 줄 순서를 지킨다.
(발견 사실: `AUTH_CALLBACK_BASE`·`COOKIE_DOMAIN`은 `core/config.py`에 있으나 `.env.example`에 없다 —
기존 누락이며 이 티켓 범위 밖이다. 고치지 않고 기록만 남긴다.)

---

## 5. 수직 슬라이스 배치 (컨벤션 강제)

새 기능은 **슬라이스당 계층별 파일 1개**다. 카카오 모바일 로그인 슬라이스:

```
apps/auth/
├── adapter/inbound/api/schemas/mobile_auth_schema.py     # 요청/응답 pydantic
├── adapter/inbound/api/v1/mobile_auth_router.py          # /auth/mobile/*
├── adapter/outbound/gateways/kakao_identity_gateway.py   # access_token_info + me (C2)
├── adapter/outbound/redis/mobile_refresh_redis_repository.py
├── app/dtos/mobile_auth_dto.py                           # frozen dataclass
├── app/ports/input/mobile_auth_use_case.py               # ABC
├── app/ports/output/kakao_identity_port.py               # ★ 명세 5.1 OIDC 교체 지점
├── app/use_cases/mobile_auth_interactor.py
├── dependencies/mobile_auth_provider.py
└── tests/app/use_cases/test_mobile_auth_interactor.py    # 스텁 포트로 검증
```

자기소개 슬라이스(`GET /auth/mobile/myself`)는 **독립 라우터**로 같은 단면을 한 벌 더 만든다.
배역·은유가 아니라 실기능(제공 엔드포인트·데이터·제약)을 설명한다.

`KakaoIdentityPort`가 명세 5.1의 교체 지점이다 — 1차는 access token 구현체 **하나만** 만들고
OIDC 구현체는 만들지 않는다(명세 9절 Non-goal + 과설계 금지).

---

## 6. 작업 순서 — 각 단계의 검증 명령

> 백엔드 검증은 **전부 도커 경유**다(호스트에 pytest·fastapi가 없다).
> 아래 마운트 경로는 이 맥 기준이다. 백엔드 PC에서는 `/home/host/projects/com.redoceanmap`.

```bash
REPO=/Users/jangminseok/Project/com.redoceanmap
TEST="docker run --rm -v $REPO:/work -w /work -e PYTHONPATH=/work/minseok:/work/minseok/apps \
      minseok97/redoceanmap-backend:latest"
```

| # | 단계 | 검증 |
| --- | --- | --- |
| 0 | **C1~C9 사용자 결정** | 결정 없이 다음으로 넘어가지 않는다 |
| 1 | `docker-compose.yaml` redis(비밀번호·헬스체크·포트 비노출) + `REDIS_URL` 동시 수정 | `docker compose up -d redis && docker compose ps` → healthy · `docker exec … redis-cli -a … ping` |
| 2 | `core/redis.py` 이중화(`get_redis_web`/`get_redis_mobile`) | `$TEST python -m pytest minseok/apps/auth -q -p no:cacheprovider` |
| 3 | users 컬럼 추가 alembic 리비전(C3) | `docker compose up -d backend` 후 `docker exec redoceanmap-pgvector-1 psql -U redocean -d redoceanmap -c '\d users'` |
| 4 | `KakaoIdentityPort` + access token 구현체(C2) | 스텁 포트 단위 테스트 — `app_id` 불일치 → 401 |
| 5 | JWT `platform`·`jti` 클레임 발급/검증 | 클레임 포함 여부 단위 테스트 |
| 6 | `require_platform` 가드(C5) | 교차 토큰 401 테스트 |
| 7 | 모바일 엔드포인트 → 웹 경로 정리 | 라우트 표 전후 diff + 전체 pytest |
| 8 | 완료 조건 기준 테스트 작성 | 아래 7절 |
| 9 | 구조 계약 확인 | `docker run --rm -v $REPO:/work -w /work/minseok -e PYTHONPATH=apps minseok97/redoceanmap-backend:latest lint-imports --config .importlinter` |

각 단계는 다음으로 넘어가기 전에 위 검증을 통과시킨다.

---

## 7. 완료 조건 — 백엔드 몫 (저장소 언어로 번역)

- [ ] 타 앱에서 발급된 카카오 토큰으로 로그인 시 **401** (`app_id` 불일치 — C2 경로로 검증)
- [ ] 모바일 액세스 토큰으로 웹 전용 엔드포인트(`/auth/web/*`) 호출 시 **401**
- [ ] 웹 액세스 토큰으로 모바일 전용 엔드포인트(`/auth/mobile/*`) 호출 시 **401**
      *(C4에서 a안을 택하면 두 항목을 `/api/{platform}/*` 기준으로 다시 쓴다)*
- [ ] 모바일 리프레시가 Redis **db 1**, 웹이 **db 0**에 저장됨
      → `docker exec … redis-cli -a … -n 1 KEYS 'mobile:*'`
- [ ] 사용된 리프레시 재사용 시 **해당 플랫폼 세션만** 전량 무효화, 타 플랫폼 세션은 유지
- [ ] `docker compose restart redis` 후에도 세션 유지(appendonly)
- [ ] 카카오 API 무응답 시 로그인만 실패하고 기존 JWT 검증은 정상
      → 게이트웨이 타임아웃 스텁으로 재현
- [ ] 로그인 실패 응답이 "미가입"과 "토큰 무효"를 구분해 노출하지 않는다
- [ ] 로그에 토큰 원문이 남지 않는다
- [ ] `lint-imports` 5종 계약 통과 · `pytest minseok/apps` 전량 통과

클라이언트 몫(`me()` 미호출 등)은 [[flutter/_docs/flutter-kakao-oauth-harness|flutter 문서]]에서 검증한다.

---

## 8. 구현 결과 — `POST /auth/mobile/kakao` (2026-08-03)

### 8.1 만든 것

```
apps/auth/
├── adapter/inbound/api/schemas/mobile_auth_schema.py        # accessToken·deviceId → accessToken·refreshToken
├── adapter/inbound/api/v1/mobile_auth_router.py             # POST /auth/mobile/kakao (rate limit 10/60s)
├── adapter/inbound/api/v1/mobile_gatekeeper_router.py       # GET /auth/mobile/myself (라우터 컨벤션)
├── adapter/outbound/gateways/kakao_identity_gateway.py      # access_token_info → app_id 검증 → me → service_terms
├── adapter/outbound/redis/mobile_refresh_redis_repository.py# db 1 · mobile:refresh / mobile:devices
├── app/dtos/mobile_auth_dto.py · mobile_gatekeeper_dto.py
├── app/ports/input/mobile_auth_use_case.py · mobile_gatekeeper_use_case.py
├── app/ports/output/kakao_identity_port.py · mobile_refresh_repository.py · mobile_gatekeeper_record_port.py
├── app/use_cases/mobile_auth_interactor.py · mobile_gatekeeper_interactor.py
├── dependencies/mobile_auth_provider.py · mobile_gatekeeper_provider.py
└── tests/ … test_mobile_auth_interactor.py(7) · test_kakao_identity_gateway.py(4) · test_mobile_gatekeeper_interactor.py(1)
```

공용부: alembic `c9d0e1f2a3b4`(users에 `kakao_id` UNIQUE·`last_login_at` 추가, `email` NULL 허용),
`core/redis.py` 이중화(`get_redis_mobile`), `core/config.py`(`KAKAO_APP_ID`·`REDIS_URL_MOBILE`),
`.env.example`, `docker-compose.yaml`(auth에 `REDIS_URL_MOBILE`), `auth_main.py` 라우터 등록.

### 8.2 확정한 결정

| 항목 | 결정 |
| --- | --- |
| C2 앱 소유권 | `access_token_info`로 `app_id`+`id` 확인 후 `/v2/user/me`로 프로필 보강 |
| C3 유저 테이블 | 컬럼 추가로 처리. `nickname`/`profile_image`는 기존 `name`으로 충당(중복 컬럼 없음) |
| C7 저장 구조 | 리프레시를 JWT로 만들지 않는다 — 랜덤 문자열이 곧 `jti`. denylist는 8.5에서 추가 |
| C8 약관 | 카카오싱크 필수 3종 동의면 즉시 가입, 아니면 가입하지 않고 **403**(동의 절차 필요) |
| 리프레시 토큰 형식 | `"{user_id}.{jti}"` — 저장 키가 `mobile:refresh:{user_id}:{jti}`라 갱신 때 user_id가 필요하다 |
| JWT 클레임 | `sub`·`platform`·`exp`. 액세스 토큰 `jti`는 denylist 도입 시 추가한다(지금 넣지 않는다) |

### 8.3 검증 (2026-08-03 실행)

| 검증 | 결과 |
| --- | --- |
| `pytest minseok/apps -m "not ollama and not network"` | 858 passed / 4 failed |
| ↑ 실패 4건 | **변경 전(HEAD 워크트리)에서도 동일하게 실패** — 이 맥의 `.env` 공개키와 `.env.auth` 개인키가 **짝이 맞지 않는다**(환경 문제) |
| `lint-imports` | 5 contracts kept, 0 broken |
| 마이그레이션 | 일회용 DB에 전체 적용 후 `\d users`로 `kakao_id` UNIQUE·`email` nullable 확인 |
| 기동 + 실호출 | `GET /auth/mobile/myself` 200 · 잘못된 카카오 토큰 → 401(일반 메시지) · `deviceId` 누락 → 422 |

### 8.4 아직 없는 것

- `POST /auth/mobile/logout` — 앱이 세션을 능동적으로 끊을 수단이 없다(현재는 만료를 기다린다).
- `require_platform` 가드(C5) — 모바일/웹 토큰 교차 사용 차단은 아직 걸려 있지 않다.

### 8.5 구현 결과 — `POST /auth/mobile/refresh` (2026-08-03)

앱 부팅 시 세션 복원 경로다(`flutter/app/lib/auth.dart`의 `Session.restore`가 이 경로를 부른다).
요청 `{ "refreshToken": "…" }` → 응답 `{ "accessToken": "…", "refreshToken": "…" }`, 실패는 401.
기존 슬라이스에 계층별로 얹었고 새 파일은 없다.

**회전** — 갱신 때마다 새 `jti`를 발급하고 쓴 토큰은 즉시 지운다. 앱은 응답의 `refreshToken`으로
저장값을 덮어써야 한다. `deviceId`는 요청에서 받지 않고 저장된 값을 물려준다(클라이언트가 갱신
시점에 바꿔 보낼 수 있으면 기기 목록이 위조된다).

**재사용 탐지** — 회전으로 폐기한 `jti`를 `mobile:denylist:{jti}`(원래 만료 시각까지)에 남긴다.
denylist에 있는 토큰이 다시 오면 사본이 도는 것으로 보고 `revoke_all`로 **그 유저의 모바일 세션만**
전량 폐기한다(웹 db 0은 건드리지 않는다 — 명세 4.4). 순서는 `deny` → `delete`다. 반대로 하면
그 틈에 도착한 재사용을 "그냥 없는 토큰"으로 흘려보낸다.

**거부 경로의 구분** — 형식 오류·저장에 없음·만료는 denylist를 건드리지 않고 401만 낸다.
남의 `user_id`를 넣어 전량 폐기를 유발하는 공격이 성립하면 안 되기 때문이다. 정지 계정은 세션이
살아 있어도 갱신되지 않는다(`ensure_active`). 실패 메시지는 사유와 무관하게 한 문장으로 고정한다.

| 검증 (2026-08-03 실행) | 결과 |
| --- | --- |
| `pytest minseok/apps/auth` | 71 passed (모바일 인터랙터 +6: 회전·기기승계·재사용전량폐기·미존재·형식오류·정지계정) |
| `pytest minseok/apps -m "not ollama and not network"` | 901 passed |
| `lint-imports` | 5 contracts kept, 0 broken |
| Redis 어댑터 실측 | 실제 Redis db15에서 save→find(TTL 승계)·deny→is_denied·delete(역인덱스 srem)·revoke_all 확인 |

---

### 8.6 구현 결과 — `POST /auth/mobile/consent` (2026-08-03)

**왜 필요했나.** iOS 시뮬레이터 실측에서 `service_terms`가 `{"msg":"permission denied","code":-5}`를
돌려줬다 — 카카오싱크는 **비즈니스 앱 전환**을 해야 열린다. 그래서 `_agreed_tags`가 항상 빈 집합이 되고
신규 유저는 전원 동의 게이트에 막힌다. 카카오 심사에 일정을 걸지 않기 위해 **동의를 우리 앱 화면에서
받는 경로**를 만들었다. 둘은 배타적이지 않다 — 나중에 카카오싱크가 열리면 `terms_agreed=True`로
들어와 이 경로를 건너뛴다.

**흐름.** `/kakao`(신규 + 동의 미확인) → `status="consent_required"` + `consentToken` →
앱이 자체 동의 화면 → `/consent` → 가입 + 세션 발급.

| 결정 | 내용 |
| --- | --- |
| 동의 필요를 **200**으로 | 실패가 아니라 절차의 한 단계다. 오류 본문(403 detail)에 다음 단계용 토큰을 싣는 형태를 피한다 |
| 동의 토큰 | 웹과 같은 방식 — RS256 JWT에 신원을 서명해 보관(DB·Redis 안 씀), 수명 10분(`CONSENT_TOKEN_EXPIRE_MINUTES` 공유) |
| `purpose="mobile_consent"` | 웹의 `social_consent`와 가른다. 안 그러면 웹 동의 토큰으로 모바일 계정을 만들 수 있다 |
| 클레임 | `kakao_id`·`email`·`nickname` — 서버가 카카오에 직접 확인한 값만. 요청 본문으로 `kakao_id`를 받지 않는다(남의 회원번호로 가입 방지) |
| 마케팅 동의 | 카카오가 아니라 **앱 동의 화면에서 받은 값**을 기록한다 |
| 동의 시각 | `/consent` 요청이 도달한 시점 |

**⚠️ `/kakao`의 응답 계약이 바뀌었다(파괴적).** `MobileSessionResponse`가
`{status, accessToken?, refreshToken?, consentToken?}`로 바뀌어 토큰 필드가 옵셔널이다.
`auth.dart:107`의 `_authenticate`는 `json['accessToken']`을 곧바로 String으로 캐스팅하므로
**서버만 먼저 배포하면 앱이 널 캐스팅으로 죽는다.** 서버 배포와 Flutter 수정은 함께 나가야 한다.

| 검증 (2026-08-03 실행) | 결과 |
| --- | --- |
| `pytest minseok/apps/auth` | 77 passed (+6: 가입·이름폴백·웹토큰투입·만료/위조·동시가입·정지계정) |
| `lint-imports` | 5 contracts kept, 0 broken |

### 8.7 남은 것

- Flutter 동의 화면 + `auth.dart`의 `consent_required` 분기(맥 작업, iOS 실기기 검증 포함).
- 카카오싱크(비즈니스 앱) 전환은 선택 사항이 됐다 — 하면 동의 화면을 건너뛴다.

---

## 9. 범위 밖

명세 9절 그대로: 카카오 외 소셜 신규 구현, 카카오 API 연동 기능(친구·메시지), 회원 탈퇴/연결 끊기,
관리자 인증. 여기에 더해 **OIDC 구현체**(포트만 두고 구현하지 않는다)와
**`/api/{platform}/*` 전면 도입**(C4에서 a안이 선택되면 별도 티켓)을 범위 밖으로 둔다.
