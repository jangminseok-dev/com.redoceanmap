# AUTH-GATEWAY-HARNESS (redoceanmap 수정판)

Claude Code 작업 지시서 — 인증 게이트웨이(auth.redoceanmap.com) 분리 배포
대상 저장소: com.redoceanmap 모노레포 (`minseok/` FastAPI 백엔드 + `www/` Next.js)
원본: `auth-gateway-harness.md`(ragtailor 프로젝트용) — 본 문서가 이 프로젝트의 유일한 기준이다.

**핵심 원칙: 발급은 auth 컨테이너에서만(개인키 보유), 백엔드는 검증만(공개키만 보유).**

---

## 0. 컨텍스트 — 현재 상태 (2026-07-22 확인)

- 엔트리포인트는 `minseok/main.py` 하나. auth 스포크(라우터 3개: auth·social·gatekeeper, 전부 prefix `/auth`)를 포함해 전 앱이 한 컨테이너(`backend`, 호스트 포트 8000)에 떠 있다.
- JWT는 **HS256 대칭키**(`JWT_SECRET`)를 발급부(auth·social 인터랙터)와 검증부(`core/security.py`)가 공유한다.
- `apps/auth`는 이미 완성된 헥사고날 스포크다 — 로그인/가입/소셜 OAuth(google·kakao·naver)/리프레시 회전(Redis·PG 어댑터)/등급(basic 자동 부여)까지 구현돼 있다. **auth 앱을 새로 만드는 작업이 아니다.**
- cloudflared 터널 `redoceanmap`은 **로컬 관리형**(백엔드 PC의 config 파일) — `api.redoceanmap.com → localhost:8000`, `n8n.redoceanmap.com → localhost:5678`. cloudflared는 호스트에서 돌고 서비스들은 호스트 포트를 노출하는 방식이다(원본 지시서의 "ports 금지" 규칙은 이 환경에 맞지 않아 폐기).
- 프론트(`www`)는 `next.config.ts` rewrites로 `/api/backend/:path*` → 백엔드에 프록시한다.

목표: 같은 코드베이스에서 엔트리포인트를 분리해 `auth.redoceanmap.com`(인증 전용, 포트 9000)과 `api.redoceanmap.com`(비즈니스, 포트 8000)을 별도 컨테이너로 운영하고, JWT를 RS256 비대칭키로 전환한다.

## 1. 절대 규칙 (위반 시 작업 중단 후 보고)

1. 기존 프로젝트 컨벤션을 그대로 따른다 — 헥사고날 레이어(`adapter → app → domain`), 스타 토폴로지(스포크→스포크 금지), `.importlinter` 계약. auth 외 스포크·허브 코드는 수정하지 않는다.
2. JWT 검증부의 허용 알고리즘은 `algorithms=["RS256"]` **리터럴 하드코딩**. 환경변수·설정으로 빼지 않는다.
3. 개인키를 읽는 함수(`jwt_private_key()`)의 호출은 **발급 코드(auth·social 인터랙터의 encode 지점)에만** 존재해야 한다. 검증 경로에서 개인키 참조 발견 시 즉시 수정.
4. 키·secret을 저장소에 커밋하지 않는다. `.env.auth`, `*.pem`을 `.gitignore`에 추가.
5. **roles/permission을 JWT 클레임에 넣지 않는다** — RBAC은 매 요청 DB 조회(`require_permission`) 유지. 역할 회수 즉시 반영은 2026-07-21 운영 결정이다.
6. **쿠키를 발급하지 않는다** — Bearer 헤더 방식 유지(쿠키 전환은 보류 결정됨). `COOKIE_KWARGS` 류 코드 작성 금지.
7. 다른 스포크가 `auth`를 import하는 코드를 작성하지 않는다. 스포크가 쓸 수 있는 것은 `core.security`뿐(기존과 동일).

## 2. 작업 목록

### 2.1 키 생성 스크립트 `minseok/scripts/generate_jwt_keys.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
echo "JWT_PRIVATE_KEY_B64=$(base64 < jwt_private.pem | tr -d '\n')"   # → .env.auth
echo "JWT_PUBLIC_KEY_B64=$(base64 < jwt_public.pem | tr -d '\n')"     # → .env (전 컨테이너 공용)
```

- 멀티라인 PEM은 env로 다루기 어려우므로 base64 단일 라인로 주입하고 config에서 디코드한다.
- `jwt_private.pem`, `jwt_public.pem`, `.env.auth`를 `.gitignore`에 추가.

### 2.2 `core/config.py` — 키 로딩 전환

```python
# env 조회는 전역 비밀값 관리자를 경유한다(core/key/secret_manager.py — 로드 지점은 그곳 하나뿐).
_secrets = get_secret_manager()

# 검증용 공개키 — 전 컨테이너 공용. 로드 시점 필수(없으면 기동 실패가 맞다).
JWT_PUBLIC_KEY = base64.b64decode(_secrets.require("JWT_PUBLIC_KEY_B64")).decode()

# 발급용 개인키 — auth 컨테이너 전용. 반드시 "호출 시점"에 읽는다:
# backend 컨테이너는 이 env가 없어도 모듈 import·기동이 되어야 한다.
# 값은 `.env.auth`를 load_auth_env()로 명시 로드한 프로세스에서만 잡힌다.
def jwt_private_key() -> str:
    raw = _secrets.get("JWT_PRIVATE_KEY_B64")
    if not raw:
        raise RuntimeError("JWT_PRIVATE_KEY_B64 미설정 — 토큰 발급은 auth 컨테이너에서만 가능합니다.")
    return base64.b64decode(raw).decode()
```

- 기존 `JWT_SECRET` 상수는 이 커밋에서 제거하지 말고, 2.4까지 완료된 뒤 함께 제거한다(중간 커밋에서도 전체가 동작해야 함).

### 2.3 발급부 RS256 전환 (auth 앱 내부만)

| 파일 | 변경 지점 |
|---|---|
| `apps/auth/app/use_cases/auth_interactor.py` | `_create_token` — `jwt.encode(claims, jwt_private_key(), algorithm="RS256")`, `ALGORITHM = "HS256"` 상수 제거 |
| `apps/auth/app/use_cases/social_interactor.py` | `_create_token`, `_create_consent_token` — 동일 전환 |

- 클레임 구조(`sub`, `exp`, consent의 `purpose` 등)는 변경하지 않는다. `aud`·`jti`·`kid`를 추가하지 않는다(§3 참고).
- 액세스 토큰 60분, 리프레시 14일 등 기존 수명 유지.

### 2.4 검증부 RS256 전환

| 파일 | 변경 지점 |
|---|---|
| `core/security.py` | `get_current_user_id` — `jwt.decode(token, JWT_PUBLIC_KEY, algorithms=["RS256"])`, `ALGORITHM` 상수 제거 |
| `apps/auth/app/use_cases/auth_interactor.py` | `_decode_token`(get_me·get_tabs 경유) — 공개키 검증 |
| `apps/auth/app/use_cases/social_interactor.py` | `_decode_consent_token` — 공개키 검증 |

- 세 곳 모두 `algorithms=["RS256"]` 리터럴. 이 시점에 `JWT_SECRET`을 config·코드·`.env`에서 완전히 제거한다.
- `get_current_user_id`의 매 요청 계정 상태 검사(정지/탈퇴 즉시 차단)와 트랜잭션 즉시 rollback은 **그대로 유지**한다.

### 2.5 `requirements.txt`

- `python-jose==3.5.0` → `python-jose[cryptography]==3.5.0` (RSA 서명/검증 백엔드).

### 2.6 `minseok/auth_main.py` 신규 (main.py 옆)

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps"))

# lifespan: main.py와 동일 패턴 — init_engine / dispose_engine + dispose_redis
# CORS: main.py와 동일(allow_origins localhost:3000) — 개발 환경 동등성
app = FastAPI(title="redoceanmap Auth", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth_router)        # /auth/register·login·refresh·me·tabs
app.include_router(social_router)      # /auth/social — OAuth 코드 교환·동의
app.include_router(gatekeeper_router)  # /auth/myself — 자기소개(프랙탈)

@app.get("/health")
def health(): ...
```

- auth 3개 라우터만 include한다. 허브 `dependency_overrides`는 불필요(어드민 라우터가 없으므로).
- `/health`는 main.py와 동일 스타일(원본의 `/healthz` 대신 프로젝트 기존 관례를 따른다).

### 2.7 `main.py` 수정 (최소 변경)

- `auth_router`·`social_router`·`gatekeeper_router` include 3줄과 해당 import만 제거한다.
- **유지할 것 (제거 금지):** `app.dependency_overrides[get_member_directory_port] = get_member_directory_gateway`, `[get_grade_policy_port] = get_grade_policy_gateway` — 어드민이 소비하는 auth 게이트웨이 주입이다. DB 조회 코드일 뿐 개인키와 무관하며, 같은 이미지를 쓰므로 backend 프로세스에서 계속 동작한다. "발급은 auth에서만"은 코드 부재가 아니라 **개인키 env 부재**로 강제된다.
- `get_current_user_id` 가드 구성(공개 화이트리스트·`_authenticated`)은 변경하지 않는다.

### 2.8 `docker-compose.yaml` — auth 서비스 추가

```yaml
  auth:
    build:
      context: ./minseok
      dockerfile: Dockerfile
    ports:
      - "9000:9000"            # cloudflared(호스트)가 localhost:9000으로 접근 — 기존 api·n8n과 동일 패턴
    volumes:
      - ./minseok:/app
    env_file:
      - .env                   # 공용 (JWT_PUBLIC_KEY_B64 포함)
      - .env.auth              # auth 전용 (JWT_PRIVATE_KEY_B64, OAuth client secrets)
    environment:
      - ENV=development
      - DATABASE_URL=postgresql://${POSTGRES_USER:-redocean}:${POSTGRES_PASSWORD:-redocean}@pgvector:5432/${POSTGRES_DB:-redoceanmap}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      pgvector:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn auth_main:app --host 0.0.0.0 --port 9000 --reload
```

- **auth는 `alembic upgrade`를 실행하지 않는다** — 마이그레이션은 backend 소유(이중 실행 경합 방지).
- backend 서비스는 수정하지 않는다(`.env`에서 `JWT_SECRET` 제거·`JWT_PUBLIC_KEY_B64` 추가는 §5의 사용자 수동 작업).

### 2.9 `www/next.config.ts` — auth 프록시 분기

```ts
const AUTH_BASE = process.env.NEXT_PUBLIC_AUTH_URL ?? "http://127.0.0.1:9000";
// rewrites: 구체 규칙이 일반 규칙보다 앞에 와야 한다.
{ source: "/api/backend/auth/:path*", destination: `${AUTH_BASE}/auth/:path*` },
{ source: "/api/backend/:path*",      destination: `${API_BASE}/:path*` },
```

- auth 라우터 3개가 전부 prefix `/auth`이므로 이 한 줄로 분기가 끝난다. 프론트 호출 코드는 무수정.
- `www/` 내 `route.ts` 핸들러가 auth 엔드포인트를 직접 호출하는 곳이 있는지 grep으로 확인하고, 있으면 같은 방식으로 base만 교체한다(로직 무수정).

### 2.10 테스트

- **기존 수정:** `tests/test_security_guard.py`, `tests/test_permission_guard.py` — HS256 토큰 민팅을 테스트 전용 RSA 키쌍 fixture로 교체(공개키는 env `JWT_PUBLIC_KEY_B64`에 monkeypatch). auth 인터랙터 테스트도 동일 fixture 적용.
- **신규 (backend 검증부 대상):**
  - auth 발급(개인키) → `get_current_user_id`(공개키만) 검증 통과 — 교차 검증 왕복.
  - 만료 토큰 401.
  - 서명 변조(페이로드 1바이트 변경) 토큰 401.
  - `alg=none` 토큰, 공개키를 비밀키 삼은 HS256 강제 서명 토큰 각각 401 — 알고리즘 혼동 공격 방어.
- 기존 리프레시 회전 테스트는 회귀 없이 통과해야 한다(리프레시 토큰은 JWT가 아니라 불투명 문자열이므로 이번 전환과 무관).

## 3. 범위 밖 — 하지 않는다 (원본 지시서에서 의도적으로 제외)

| 원본 항목 | 제외 사유 |
|---|---|
| `apps/auth/` flat 신규 생성 (router.py·services.py·rbac.py) | 이미 헥사고날로 완성돼 있음. flat 구조는 슬라이스 1:1 컨벤션 위반 |
| roles 클레임 + `RoleChecker` | 기존 `require_permission`(매 요청 DB 조회)이 상위 호환 — 역할 회수 즉시 반영 |
| Redis jti 블랙리스트 | `get_current_user_id`의 매 요청 users 상태 검사가 이미 즉시 차단을 보장 |
| httponly 쿠키 발급 | 쿠키 전환 보류 결정(2026-07-21) 유지 |
| `aud` 클레임 (서비스별 상이) | 검증자가 backend 하나뿐. consent 토큰 혼동 방지는 기존 `purpose` 클레임이 담당 |
| JWKS (`/.well-known/jwks.json`) | 공개키는 env로 배포하면 충분. 외부 검증자가 생기면 후속 작업 |
| 액세스 토큰 10분 단축 | 매 요청 DB 상태 검사로 정지 반영 지연 문제가 이미 없음. 60분 유지 |
| `.importlinter` auth-isolation 계약 추가 | 기존 "스포크 상호 독립" 계약이 이미 커버. 변경 없음 확인만 한다 |
| 리프레시 재사용 감지 시 세션 전체 폐기 | **2026-10-05 구현** — 회전 기록은 ORM이 아니라 Redis(`auth:refresh-rotated:`)에 원래 만료까지 남긴다. 회전 30초 뒤의 재사용만 탈취로 보고 웹 세션 전량 폐기(동시 갱신 오탐 방지) → auth CLAUDE |

## 4. 전환 시 주의 (마이그레이션)

- RS256 배포 순간 기존 HS256 **액세스 토큰·소셜 동의 토큰은 전부 무효**가 된다. 리프레시 토큰(불투명 문자열)은 유효하므로 프론트가 `/auth/refresh`로 자동 복구된다 — 실패 시 재로그인 1회. 별도 병행 검증 기간은 두지 않는다(단일 서비스, 사용자 소수).
- 커밋 순서상 2.3~2.4 완료 시점(엔트리 분리 전)에는 단일 컨테이너가 개인키+공개키를 모두 가진 채 동작한다 — 이 상태로도 전체 기능이 정상이어야 한다.

## 5. 수동 적용 필요 (사용자 — 코드 밖, 작업 완료 보고서에 그대로 출력)

1. **키 생성:** 백엔드 PC에서 `scripts/generate_jwt_keys.sh` 실행.
2. **`.env` 편집:** `JWT_PUBLIC_KEY_B64=...` 추가. 2.4 배포 후 `JWT_SECRET` 줄 삭제.
3. **`.env.auth` 생성:** `JWT_PRIVATE_KEY_B64=...` + `GOOGLE_CLIENT_SECRET`·`KAKAO_CLIENT_SECRET`·`NAVER_CLIENT_SECRET`(및 대응 CLIENT_ID)을 `.env`에서 이동 — backend 컨테이너에서 OAuth secret 제거.
4. **cloudflared (백엔드 PC, 로컬 관리형 터널):**
   - config 파일(`~/.cloudflared/config.yml` 상당) ingress에 catch-all(`http_status:404`)보다 위에 추가:
     ```yaml
     - hostname: auth.redoceanmap.com
       service: http://localhost:9000
     ```
   - DNS 연결(1회): `cloudflared tunnel route dns redoceanmap auth.redoceanmap.com`
   - cloudflared 서비스 재시작 → 대시보드 Routes에 세 번째 줄 확인 → `https://auth.redoceanmap.com/health` 200 확인.
5. **프론트 배포 env:** `NEXT_PUBLIC_AUTH_URL` 설정 — www가 백엔드 PC에서 돌면 `http://localhost:9000`(내부 경유, 권장), 외부면 `https://auth.redoceanmap.com`.

## 6. 완료 기준 (Acceptance Criteria)

- [ ] `uvicorn auth_main:app` 단독 기동 성공, `/health` 200, `/auth/myself` 정상 응답.
- [ ] `JWT_PRIVATE_KEY_B64` **없이** `uvicorn main:app` 기동 성공(import 에러 없음), 보호 라우터가 공개키만으로 검증 동작.
- [ ] auth 컨테이너에서 로그인 → 발급 토큰으로 backend 보호 엔드포인트 호출 성공 (교차 검증 왕복).
- [ ] 만료·서명 변조·`alg=none`·HS256 강제 토큰 각각 거부하는 테스트 존재·통과 (2.10).
- [ ] 소셜 로그인(동의 토큰 포함)·리프레시 회전·`/auth/tabs` 회귀 없음.
- [ ] `pytest` 전체 통과, `lint-imports` 통과(계약 변경 없음).
- [ ] 코드 전체에서 `JWT_SECRET`·`HS256` 문자열 grep 결과 0건 (테스트의 공격 시나리오 제외).

## 7. 진행 방식

1. 작업 전 `core/security.py`, `core/config.py`, 두 인터랙터, `main.py`, `docker-compose.yaml` 현재 상태를 읽고 요약 보고 후 시작.
2. 커밋 단위 (각 커밋에서 전체 동작 유지):
   - ① 2.1 + 2.2 + 2.5 — 키 인프라 (JWT_SECRET 병존)
   - ② 2.3 + 2.4 + 2.10 — RS256 전환 + JWT_SECRET 제거 (아직 단일 컨테이너)
   - ③ 2.6 + 2.7 + 2.8 — 엔트리포인트·컨테이너 분리
   - ④ 2.9 — 프론트 프록시 분기
3. 불명확한 지점(예: www 내 auth 직접 호출 지점의 처리 방식)은 추측하지 말고 질문한다.
