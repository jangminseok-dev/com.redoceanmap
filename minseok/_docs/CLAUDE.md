# CLAUDE.md — 백엔드 (minseok)

공통 원칙 → [[CLAUDE|CLAUDE (루트)]] · 엔티티 규칙 → [[minseok/_docs/ENTITY_RULES|ENTITY_RULES]] · 로드맵 → [[minseok/_docs/ROADMAP|ROADMAP]]

Python / FastAPI 백엔드. 앱 **내부**는 헥사고날/클린 아키텍처(`adapter → app → domain`),
앱 **사이**는 스타 토폴로지(허브-스포크)를 따른다. 두 구조는 `minseok/.importlinter`로 강제된다.

---

## 자동 적용 규칙

작업 영역에 해당하면 사용자 지시 없이 아래 문서의 규칙을 먼저 읽고 적용한다.

| 문서                                           | 적용 시점                                                            |
| -------------------------------------------- | ---------------------------------------------------------------- |
| [[minseok/_docs/ENTITY_RULES\|ENTITY_RULES]] | 엔티티/ORM(테이블)을 정의·수정할 때 — SQLAlchemy 2.0 스타일, `int` 타입 단일 PK `id` |
| 아래 "라우터 컨벤션"                                 | 새 라우터를 만들 때 — 실기능 자기소개 `/myself` + 프랙탈 단면 필수                     |

## 라우터 컨벤션 — 실기능 자기소개 + 프랙탈 (필수)

새 라우터를 만들 때는 반드시 다음을 함께 만든다:

1. **`GET <prefix>/myself` 자기소개 엔드포인트** — 배역/은유가 아니라 **실제 기능**을 설명한다
   (제공 엔드포인트·데이터·제약을 명시. 예: "매매 지시는 하지 않습니다").
2. **프랙탈 단면** — 자기소개도 전체 헥사고날 단면을 관통한다:
   ```
   adapter/inbound/api/schemas/<이름>_schema.py     # 요청/응답 pydantic 스키마
   app/dtos/<이름>_dto.py                            # Query·Response (frozen dataclass)
   app/ports/input/<이름>_use_case.py                # UseCase ABC
   app/ports/output/<이름>_record_port.py            # 활동 기록 아웃바운드 포트
   app/use_cases/<이름>_interactor.py                # 대장 — record 포트를 실제 사용
   adapter/outbound/log_<이름>_record_adapter.py     # 임시 로그 구현 (영속 필요 시 PG 교체)
   dependencies/<이름>_provider.py                   # DI 프로바이더
   tests/app/use_cases/test_<이름>_interactor.py     # 스텁 포트로 검증
   ```
3. **유스케이스는 어댑터 스키마가 아니라 app DTO를 받는다** (계층 계약 — 스키마↔DTO 변환은 라우터 몫).
4. 아웃바운드 포트는 빈 껍데기 금지 — 인터랙터가 실제 호출하는 형태로 만든다.

---

## 스타 토폴로지 — 앱 사이 구조 (허브-스포크)

- **허브 = `apps/hub`** — 앱 간 협력의 단일 교차점. 계약(포트+DTO)만 소유. → [[minseok/apps/hub/_docs/CLAUDE|hub CLAUDE]]
- **스포크 = `hub`를 제외한 `apps/` 전부** — 허브가 공개한 추상에만 의존하는 독립 도메인 노드.

| 방향 | 허용 | 이유 |
|------|------|------|
| 스포크 → 허브 | ✅ | 스포크는 허브 포트/DTO에만 의존 |
| 스포크 → 스포크 | ⛔ | 직접 import·순환 금지. 교차 협력은 허브 경유 |
| 허브 → 스포크 | ⛔ | 허브가 특정 스포크를 알면 스타가 메시로 무너짐 |

`core/`는 순수 인프라 공유(DB 세션·`Base`·config)만 담당하며 도메인 협력은 허브가 맡는다.
정적 강제·검증 → harness 문서(`_docs/harness.md`).

## 앱 지도

| 앱 | 유형 | 문서 |
| --- | --- | --- |
| hub | 허브 | [[minseok/apps/hub/_docs/CLAUDE\|hub CLAUDE]] |
| market | 스포크 | [[minseok/apps/market/_docs/CLAUDE\|market CLAUDE]] |
| chat | 스포크 | [[minseok/apps/chat/_docs/CLAUDE\|chat CLAUDE]] |
| auth | 스포크 | [[minseok/apps/auth/_docs/CLAUDE\|auth CLAUDE]] |
| recommendation | 스포크 | [[minseok/apps/recommendation/_docs/CLAUDE\|recommendation CLAUDE]] |
| stock | 스포크 | [[minseok/apps/stock/_docs/CLAUDE\|stock CLAUDE]] |
| mail | 스포크 | [[minseok/apps/mail/_docs/CLAUDE\|mail CLAUDE]] |
| admin | 스포크 | [[minseok/apps/admin/_docs/CLAUDE\|admin CLAUDE]] |

새 앱은 `minseok/apps/<app>/_docs/CLAUDE.md` + 심볼릭 링크 `<app>/CLAUDE.md → _docs/CLAUDE.md`를
추가하고 위 표에 한 줄 등록한다.

---

## 앱 내부 레이어 (헥사고날)

```
<app>/
├── domain/{entities,value_objects}/   # 순수 도메인 — 외부 의존 금지
├── app/
│   ├── ports/{input,output}/          # UseCase / Repository ABC
│   ├── use_cases/                     # Interactor (대장)
│   └── dtos/                          # 레이어 간 전달 객체
├── adapter/
│   ├── inbound/api/{schemas,v1}/      # Pydantic 스키마 · FastAPI 라우터
│   └── outbound/{orm,pg,mappers,gateways}/
├── dependencies/                      # FastAPI DI 프로바이더
└── tests/
```

**의존 방향:** `adapter → app → domain` (역방향 금지). 어댑터 스키마를 app에서 직접 import하면
계층 역전 — 필요하면 `app/dtos` 또는 `TYPE_CHECKING` 가드를 쓴다.

## 임포트 / 세션 규칙

- 앱은 최상위 패키지로 인식된다(`from market.app.ports... import ...`). `main.py`가
  `sys.path`에 `apps/`를 등록하고, lint/스크립트는 `PYTHONPATH=apps`로 맞춘다.
- 세션·베이스: `from core.database import get_db, Base`.
- LLM 추론은 단일 LLM 오케스트레이터 `core/llm/llm_orchestrator.py`로 수렴한다 —
  오케스트레이터가 EXAONE 7.8B 하나만 보유한다(단일 모델 정책, 2026-07-15).
- **비밀값·환경 변수는 `core/key/secret_manager.py`로 수렴한다** — 아래 참고.

## 비밀값 규칙 — `.env` 로드는 한 곳에서만 (필수)

`load_dotenv`를 직접 부르는 곳은 `core/key/secret_manager.py` **하나뿐이다**. 새 스크립트·
엔트리포인트·마이그레이션을 추가할 때 `load_dotenv`나 `os.getenv`를 다시 쓰지 않는다.

| 쓰는 쪽 | 방법 |
|---|---|
| 앱 런타임(어댑터·프로바이더·유스케이스) | `from core.config import ...` — 상수만 소비, 관리자를 직접 부르지 않는다 |
| 스크립트 · 마이그레이션 · 엔트리포인트 | `get_secret_manager().get(name, default)` / `.require(name)` |
| 새 설정값 추가 | `.env.example`에 키 등록 → `core/config.py`에 상수 한 줄 |

- `core/config.py`는 `DATABASE_URL`·`JWT_PUBLIC_KEY_B64`를 필수로 요구한다. 이 둘 없이
  돌아야 하는 스크립트는 `core.config` 대신 관리자를 직접 쓴다(`core/key/s3_manager.py`가 사례).
- **개인키 경계:** `.env.auth`(`JWT_PRIVATE_KEY_B64`)는 자동 로드되지 않는다.
  `load_auth_env()`를 명시 호출한 프로세스(`auth_main.py` · `conftest.py`)만 본다 —
  백엔드 프로세스는 토큰을 발급할 수 없어야 한다. 회귀 방지: `tests/test_secret_manager.py`.

## LLM 모델 계층 바인딩

| 지점 | 모델 |
|------|------|
| 도메인 내부 추론(예: chat phase1 상권/업종 선택) | EXAONE **7.8B** (단일 모델 정책 — 2.4B 폐지) |
| 최종 사용자 답변(예: chat phase2·스트리밍) | EXAONE **7.8B** (오케스트레이터 기본) |

## async def vs def

I/O-bound(DB·LLM·HTTP)는 `async def`, CPU-bound(수치·변환)는 `def`. 포트(ABC)와 구현체의
`def`/`async def`를 일치시킨다. 무거운 CPU 작업은 호출 측에서 `asyncio.to_thread`로 분리한다.
