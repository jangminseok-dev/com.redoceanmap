# CLAUDE.md — 프로젝트 루트

[Andrej Karpathy의 관찰](https://x.com/karpathy/status/2015883857489522876)을 바탕으로 한 **에이전트 하네스**다. 에이전트의 경계·검증·스코프를 고정해 침묵 가정, 과설계, 스코프 확장, 모호한 "됐다" 선언을 줄인다. 에이전트(Claude Code, Cursor, Codex 등)는 코드·설정·명령을 제안·실행하기 전에 본 문서를 먼저 읽고, 프로젝트별 지침과 병합해 해석한다.

## 언어 설정

- 항상 한국어로 응답한다.

---

## 프로젝트 개요

한 저장소에 백엔드·프론트엔드가 함께 있다.

| 영역 | 스택 | 위치 |
| --- | --- | --- |
| 백엔드 | Python 3.13 · FastAPI 0.128 · SQLAlchemy 2.0(asyncio) · Pydantic 2 · Alembic | `minseok/` |
| 인증 | 위와 동일 (별도 프로세스 `auth_main.py` — 개인키를 분리 보유) | `minseok/apps/auth` |
| 프론트엔드 | Next.js 16 · React 19 · TypeScript 5 · Tailwind 4 · zustand · TanStack Query | `www/` |
| 데이터 | PostgreSQL 17(pgvector) · Redis 7 · Neo4j | 도커 컴포즈 |
| LLM | EXAONE 3.5 7.8B 로컬 추론(Ollama) — 단일 모델 정책 | `minseok/core/llm` |

백엔드는 **모듈러 모놀리식**이다. 앱 내부는 헥사고날/클린(`adapter → app → domain`),
앱 사이는 스타 토폴로지(허브 `hub` + 스포크)이며 두 구조는 `minseok/.importlinter`로 강제된다.
프론트엔드는 브라우저 fetch를 `/api/backend` rewrite로만 백엔드에 보낸다.

---

## 하위 CLAUDE.md 링크 (WikiLink)

작업 디렉토리가 아래 영역에 속하면 해당 CLAUDE.md를 **먼저 읽고** 규칙을 적용한다.
각 영역 루트의 `CLAUDE.md`는 `_docs/CLAUDE.md`로의 **심볼릭 링크**다(실내용은 `_docs/`에).

| 영역 | 문서 |
| --- | --- |
| 백엔드 (Python / FastAPI) | [[minseok/_docs/CLAUDE\|minseok CLAUDE]] |
| 프론트엔드 (Next.js) | [[www/_docs/CLAUDE\|www CLAUDE]] |
| 모바일 (Flutter — 실기기 테스트 환경) | [[flutter/_docs/flutter-harness\|flutter harness]] |
| 하네스 (구조 검증) | [[_docs/harness\|harness]] |
| 고도화 로드맵 (3단계·18 마일스톤) | [[minseok/_docs/ROADMAP\|ROADMAP]] |

> 앱은 **스타 토폴로지**(허브 `hub` + 스포크)다. 앱별 문서는 [[minseok/_docs/CLAUDE|minseok CLAUDE]]의
> 앱 표에서 잇는다. 새 앱은 `minseok/apps/<app>/_docs/CLAUDE.md` + 심볼릭 링크
> `<app>/CLAUDE.md → _docs/CLAUDE.md`를 같은 패턴으로 추가한다.

> `flutter/`에는 아직 코드가 없고 `_docs/`만 있다. 영역 규칙 문서(`flutter/CLAUDE.md` 심볼릭 링크)는
> 코드가 들어올 때 위와 같은 패턴으로 만든다.

---

## 자동 적용 규칙 — 프론트엔드(www)

`www/` 디렉토리의 React/Next.js 코드(`.tsx` / `.ts` / `.jsx` / `.js`)를 읽거나 작성·수정할 때는 `www/_docs/REACT_RULES.md`를 먼저 읽고 자동 적용한다.

- **핵심 규칙:** 하나의 컴포넌트에 `useState`가 2개 이상이면 묻지 말고 FormData 패턴(폼 제출) 또는 단일 객체 패턴(실시간 상태)으로 압축한다.
- **예외:** 사용자가 명시적으로 "useState 유지"를 요청한 경우.
- **결과 보고:** 어떤 패턴을 적용했는지 한 줄로 명시한다.

---

## 공통 행동 원칙

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## 명령어

**호스트에 파이썬 개발 환경이 없다.** 루트 `venv/`는 cron 전용 경량, `.venv`는 EXAONE 학습 전용이며
둘 다 pytest·fastapi가 없다. 백엔드 검증은 전부 도커 경유다. node는 호스트에 있다(프론트는 직접 실행).

```bash
# 전체 스택 기동 — backend:8000 · auth:9000 · pgvector:5432 · redis:6379 · neo4j:7474/7687 · n8n:5678
# (모두 127.0.0.1 루프백 바인딩. 0.0.0.0 금지 — LAN 노출 차단)
docker compose up -d

# market 앱 전용 DB (:5434) — 공유 DB와 별개로 따로 띄운다
cd minseok/apps/market && docker compose up -d

# DB 브라우저 pgadmin (선택 기동) — http://127.0.0.1:5050
# 공유 DB·market DB 2개가 _docs/pgadmin-servers.json으로 자동 등록된다(.env에 PGADMIN_* 필요)
docker compose --profile tools up -d pgadmin

# 그래프 브라우저는 Neo4j에 내장 — http://127.0.0.1:7474 (계정은 .env의 NEO4J_USER/PASSWORD)
docker compose --profile graph up -d neo4j

# 쿠버네티스(k3s) 개발 스택 — 도커 컴포즈 대체 진행 중(2026-09-07~). 설치·포트·기동은 k8s/README.md
# 실운영 구 스택과 포트가 겹치지 않게 backend:18000 · auth:19000 · pgvector:15432 (전부 루프백)
kubectl apply -k k8s/dev

# 프론트엔드 개발 서버 (패키지 매니저는 pnpm — pnpm-lock.yaml이 정본)
cd www && pnpm run dev

# 프론트엔드 타입 체크 (test/lint 스크립트는 없다)
# npx tsc는 로컬 typescript를 못 찾으면 레지스트리의 무관한 tsc 패키지를 설치하고
# exit 0으로 끝난다(가짜 초록). 반드시 package.json 스크립트로 돌린다.
cd www && pnpm run typecheck
```

```bash
# 백엔드 테스트 전체
docker run --rm -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest python -m pytest minseok/apps -q -p no:cacheprovider

# import-linter — 아키텍처 계약 5종(클린 아키텍처 · 스포크 상호 독립 ·
#                  프레임워크 격리 · 도메인 순수성 · 허브 격리)
docker run --rm -v /home/host/projects/com.redoceanmap:/work -w /work/minseok \
  -e PYTHONPATH=apps minseok97/redoceanmap-backend:latest lint-imports --config .importlinter
```

- 마이그레이션은 `docker compose up` 시 backend 컨테이너가 `alembic upgrade head`로 자동 적용한다.
  `minseok/alembic.ini`(공유 DB)와 `minseok/apps/market/alembic.ini`(market 전용 DB)는 **독립**이다.
- 실 DB에 붙는 스크립트는 `--network host`를 추가한다(`DATABASE_URL`이 `localhost:5432`).
- psql: `docker exec redoceanmap-pgvector-1 psql -U redocean -d redoceanmap`

---

## 코딩 컨벤션

영역별 상세는 하위 문서가 정본이다. 아래는 저장소 전체에 걸리는 공통 사항이다.

| 영역 | 정본 |
| --- | --- |
| 백엔드 | [[minseok/_docs/CLAUDE\|minseok CLAUDE]] · [[minseok/_docs/ENTITY_RULES\|ENTITY_RULES]] |
| 프론트엔드 | [[www/_docs/CLAUDE\|www CLAUDE]] · [[www/_docs/REACT_RULES\|REACT_RULES]] · `.claude/rules/typescript.md` |

- **주석·문서·커밋 메시지는 한국어.** 커밋은 `type(scope): 요약` 형식(예: `fix(auth): …`).
- **백엔드:** I/O-bound는 `async def`, CPU-bound는 `def`. 포트(ABC)와 구현체의 `def`/`async def`를
  일치시킨다. 유스케이스는 어댑터 스키마가 아니라 `app/dtos`를 받는다.
- **백엔드 임계값·상수:** `load_dotenv`·`os.getenv`를 새로 쓰지 않는다 —
  `core/key/secret_manager.py`(스크립트·엔트리포인트) 또는 `core/config.py`(런타임) 경유.
- **프론트엔드:** strict mode 유지, `any` 금지(카카오맵 SDK 경계 예외), `interface`보다 `type`,
  백엔드 응답 필드명은 변환하지 않는다.
- 새 라우터는 `GET <prefix>/myself` 자기소개 + 헥사고날 프랙탈 단면을 함께 만든다(백엔드 정본 참고).

---

## 테스트

- 프레임워크: **pytest 9 + pytest-asyncio**(`asyncio_mode = auto` — `@pytest.mark.asyncio` 불필요).
- 테스트 파일: `test_*.py` 패턴, 앱별 `minseok/apps/<app>/tests/` 아래(현재 89개 파일).
- 마커(`pytest.ini`) — 기본 검증에서 빼려면 `-m "not ollama and not network"`:
  - `ollama`: 로컬 EXAONE 모델을 호출하는 통합 테스트
  - `network`: 외부 API(야후 파이낸스 등) 호출이 필요한 통합 테스트
- 유스케이스는 **스텁 포트**로 검증한다(mock 프레임워크보다 스텁 구현 선호).
- 구조 위반은 테스트가 아니라 import-linter가 잡는다. 아키텍처를 건드린 변경은 둘 다 돌린다.
- 프론트엔드에는 테스트 러너가 없다 — 검증 수단은 `npx tsc --noEmit`뿐이다.

---

## 브랜치 전략

- `main` — 프로덕션. 프론트엔드는 이 브랜치가 Vercel에 자동 배포된다.
- `window` / `mac` — 작업 기기별 브랜치. **세 브랜치(`window`·`mac`·`main`)를 항상 같은 커밋으로
  유지한다.** 작업 후 세 곳 모두에 push하고, 다른 기기에서 시작할 때 먼저 fetch한다.
- `aws` — EC2 배포용 compose가 갈라져 있는 원격 전용 브랜치. 위 3개와 동기화하지 않는다.
- 커밋·push는 사용자가 요청할 때만 한다.

---

## 환경 변수

- `.env` — 실제 값(git 제외). 키를 추가하면 **`.env.example`에도 반드시 등록**한 뒤
  `core/config.py`에 상수 한 줄을 더한다.
- `.env.auth` — JWT **개인키**(`JWT_PRIVATE_KEY_B64`) 전용. 자동 로드되지 않으며
  `load_auth_env()`를 명시 호출한 프로세스(`auth_main.py`·`conftest.py`)만 본다.
  백엔드 프로세스가 토큰을 발급할 수 없어야 하는 경계이므로 이 파일을 일반 로드 경로에 넣지 않는다.
  회귀 방지: `minseok/tests/test_secret_manager.py`.
- `www/.env.local` — 프론트엔드 전용(`NEXT_PUBLIC_*`).
- 필수: `DATABASE_URL`, `JWT_PUBLIC_KEY_B64`(`core/config.py`가 없으면 기동 거부).
  이 둘 없이 돌아야 하는 스크립트는 `core.config` 대신 `get_secret_manager()`를 직접 쓴다.
- 그 외 계열: `MARKET_DATABASE_URL`, `POSTGRES_*`, 소셜 로그인(`GOOGLE_`/`KAKAO_`/`NAVER_`),
  공공데이터(`SEOUL_OPENDATA_API_KEY`·`DATA_GO_KR_API_KEY`·`DART_API_KEY`), `AWS_*`, `NEO4J_*`.

---

## 주의사항

- **스포크끼리 직접 import 금지.** 교차 협력은 허브(`apps/hub`) 포트 경유. 허브는 스포크를 모른다.
- **공유 DB 불가침.** 앱 전용 DB(market `:5434`)와 공유 DB(`:5432`)를 섞지 않는다.
  앱 전용 테이블을 공유 DB에 만들거나 그 반대로 하지 않는다.
- **도커 스택이 2벌 공존한다.** 실행 중인 실운영 스택은 이 저장소 밖(`/home/host/projects/redoceanmap/`)의
  compose이고 컨테이너 이름이 `redoceanmap-*`(실 DB = `redoceanmap-pgvector-1`, pg16, `:5432`)이다.
  이 저장소의 compose도 `:5432`를 바인딩하므로 **그대로 올리면 실운영 DB와 포트가 충돌한다** —
  기동 전에 `docker ps`로 무엇이 떠 있는지 확인한다. 볼륨 삭제·`down -v`·스키마 파괴 명령은
  사용자 확인 없이 실행하지 않는다. 백업은 매일 04:00 cron(`scripts/backup_db.sh`).
- **cron 스크립트는 루트 `venv/`를 쓴다.** 새 cron에 `.venv`(EXAONE 학습 전용)를 쓰면 학습 환경
  정리 시 조용히 죽는다.
- **비밀값을 로그·커밋·문서에 남기지 않는다.** `.env*` 파일 내용을 그대로 출력하지 않는다.
- **프론트엔드 브라우저 fetch는 절대 URL을 쓰지 않는다** — `/api/backend` rewrite 경유.
  쿼리만 바꾸는 내비게이션은 `router.replace/push`가 프로덕션 빌드에서 무시되므로
  `history.replaceState`를 쓴다(dev에서는 재현되지 않는다).
- `minseok/EXAONE-3.5-7.8B-Instruct/`(모델 가중치)와 `minseok/data/`(원본 데이터)는 코드가 아니다.
  검색·일괄 수정 대상에서 제외한다.
