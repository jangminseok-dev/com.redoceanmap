# CLAUDE.md — hub (허브)

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

**스타 토폴로지의 허브** (ragwatson `star_craft` 패턴). 앱 간 협력의 단일 교차점.
계약(포트+DTO)에 더해 **외부 자동화(n8n)의 단일 인바운드 창구와 교차 유스케이스**를 소유한다.
ORM/DB는 갖지 않는다 — 저장·분석 등 구체 작업은 아웃바운드 포트로 스포크에 위임한다.
예외로 **비전(YOLO 얼굴 탐지·파인튜닝)** 은 특정 스포크에 속하지 않는 허브 소유 기능으로
직접 구현한다(구 vision 스포크 흡수) — 아래 "허브 소유 기능 — 비전" 참고.

---

## 허브 격리 (import-linter `허브 격리` 계약)

- 허브는 스포크를 **import하지 않는다**. 특정 스포크를 알면 허브가 비대해지고 스타가 메시로 무너진다.
- 스포크는 허브가 공개한 **추상(포트/DTO)** 에만 의존한다(스포크 → 허브 허용).
- 구체 구현은 스포크가 제공하고, `main.py`(합성 루트)가 `dependency_overrides`로 주입한다 — 의존 역전.

## 소유 계약 — CommercialDataPort

상권 데이터 조회 협력. chat(소비)과 market(구현)을 잇는다.

```
apps/hub/app/
├── ports/output/commercial_data_port.py   # CommercialDataPort (ABC)
│     get_service_codes / get_area_summary / get_area_raw_stats / get_area_scores
│     / get_area_insights / get_area_overview / get_dataset_stats
└── dtos/commercial_data_dto.py            # ServiceCode · AreaInfo · AreaSummary · AreaRawStat
│                                          #   · AreaScoreInfo · AreaScoreComponent · AreaOverviewRow
└── dtos/dataset_stat_dto.py               # DatasetStat — market·stock 공용이라 별도 모듈
apps/hub/dependencies/commercial_data_provider.py  # get_commercial_data_port (NotImplementedError 스텁)
```

`get_area_scores`는 시도 벤치마크 대비 상권 종합점수(market의 `area_scorer` 도메인 서비스,
50점=벤치마크 동률)를 반환한다 — chat이 상권 추천 서술의 근거로 주입(①-M5 잔여, 2026-07-15).
`get_area_insights`는 `area_narrator`가 만든 해석 문장(`AreaInsight`)을 나른다 — 고객층·
배후 수요·소비력·객단가. 지도 오버레이만 보던 인사이트를 chat phase2에도 공급한다(2026-07-27).

> **문장을 나르는 이유**: 허브 DTO는 원시 수치가 원칙이지만 `AreaScoreInfo.grade`("우수"/
> "주의" …)가 이미 판정 라벨을 나른다. 실제 규칙은 "허브가 문장을 *만들지* 않는다"이고,
> 문장의 소유자는 market 도메인이다. 원시로 내리면 임계값 판정이 소비자마다 중복 구현돼
> 같은 상권을 지도와 채팅이 다르게 설명하게 된다. 주입 개수 절단은 소비자(chat) 몫이다.
`get_area_overview`(전 상권 최신 분기 점포수·폐업률·월매출)와 `get_dataset_stats`(데이터셋별
행수·최신 시점)는 admin(어드민 콘솔)이 소비한다.

- **구현**: `market`의 `CommercialDataGateway`(정규화 3NF 스키마를 조인 조회) → market CLAUDE.
- **소비**: `chat`의 `ChatInteractor` → chat CLAUDE. `admin`의 area·data_source 인터랙터.
- **배선**: `main.py`에서 `app.dependency_overrides[get_commercial_data_port] = get_commercial_data_gateway`.

## 소유 계약 — MemberDirectoryPort

회원·역할(RBAC) 협력. admin(소비)과 auth(구현·영속: users + RBAC 4테이블)를 잇는다.

```
apps/hub/app/
├── ports/output/member_directory_port.py   # MemberDirectoryPort (ABC)
│     list_members / member_stats / list_roles / grant_role / revoke_role / list_user_permissions
│     / suspend / reinstate / revoke_sessions / withdraw(익명화·비가역)
└── dtos/member_directory_dto.py            # MemberInfo(suspended_at·deleted_at 포함) · MemberPage · MemberStats · RoleInfo
apps/hub/dependencies/member_directory_provider.py  # get_member_directory_port (NotImplementedError 스텁)
```

- **구현**: `auth`의 `MemberDirectoryGateway`(users·RBAC 조인 조회, 부여/회수는 멱등,
  제재는 리프레시 저장소와 협력 — 정지/탈퇴 시 토큰 전량 폐기).
- **소비**: `admin`의 member·steward·dashboard 인터랙터(회원 관리·/admin/me 권한 판정·KPI).
- **배선**: `main.py`에서 `app.dependency_overrides[get_member_directory_port] = get_member_directory_gateway`.

## 소유 계약 — GradePolicyPort

등급(=roles 재해석) 구성 협력. admin(소비)과 auth(구현·영속: roles + role_tabs)를 잇는다.
MemberDirectoryPort(회원·역할 부여/회수)와 별개인 등급 CRUD 전용 계약(Directory/Record 분리 선례).

```
apps/hub/app/
├── ports/output/grade_policy_port.py   # GradePolicyPort (ABC)
│     list_grades / create_grade / update_grade / delete_grade (중복·부재는 ValueError)
└── dtos/grade_dto.py                   # GradeInfo(code·name·tabs·member_count)
apps/hub/dependencies/grade_policy_provider.py  # get_grade_policy_port (NotImplementedError 스텁)
```

- **구현**: `auth`의 `GradePolicyGateway`. delete는 role_tabs·role_permissions·user_roles 동반 삭제.
- **소비**: `admin`의 grade 인터랙터(탭 키·code 형식 검증, admin 삭제·개명 보호, 감사 기록).
- **배선**: `main.py`에서 `app.dependency_overrides[get_grade_policy_port] = get_grade_policy_gateway`.
- 유저 개인의 노출 탭 조회(`GET /auth/tabs`)는 auth 스포크 내부 관심사 — 이 계약에 없다.

## 소유 계약 — RecommendationDirectoryPort

추천 기록 열람 협력(RecommendationRecordPort의 쓰기와 별개인 조회 전용). admin(소비)과
recommendation(구현)을 잇는다.

```
apps/hub/app/
├── ports/output/recommendation_directory_port.py   # RecommendationDirectoryPort (ABC) — list_recent / stats
└── dtos/recommendation_directory_dto.py             # RecommendationInfo(trdar_code 포함 — 본체 딥링크용)
│                                                    #   · MonthCount · CategoryCount · RecommendationStats
apps/hub/dependencies/recommendation_directory_provider.py  # get_recommendation_directory_port (NotImplementedError 스텁)
```

- **구현**: `recommendation`의 `RecommendationDirectoryGateway`(recommendations 집계).
- **소비**: `admin`의 dashboard·recommendation_log 인터랙터.
- **배선**: `main.py`에서 `app.dependency_overrides[get_recommendation_directory_port] = get_recommendation_directory_gateway`.

## 소유 계약 — RecommendationRecordPort

추천 기록 협력. chat(생성·소비)과 recommendation(구현·영속)을 잇는다.

```
apps/hub/app/
├── ports/output/recommendation_record_port.py   # RecommendationRecordPort (ABC) — record()
└── dtos/recommendation_record_dto.py             # RecommendedArea (저장 전 초안)
apps/hub/dependencies/recommendation_record_provider.py  # get_recommendation_record_port (NotImplementedError 스텁)
```

- **구현**: `recommendation`의 `RecommendationRecordGateway`(허브 DTO → 도메인 초안 변환 후 유스케이스 위임) →
  recommendation CLAUDE.
- **소비**: `chat`의 `ChatInteractor`가 phase2 추천 생성 직후 `record()` 호출.
- **배선**: `main.py`에서 `app.dependency_overrides[get_recommendation_record_port] = get_recommendation_record_gateway`.

## 소유 계약 — StockAnalysisPort

주식 분석 협력. chat(소비)과 stock(구현)을 잇는다.

```
apps/hub/app/
├── ports/output/stock_analysis_port.py   # StockAnalysisPort (ABC) — analyze(query)
│     실패는 StockAnalysisUnavailable(계약 예외)로 알린다
└── dtos/stock_analysis_dto.py            # StockAnalysisResult (원시 수치 — 문장화는 소비자 몫)
apps/hub/dependencies/stock_analysis_provider.py  # get_stock_analysis_port (NotImplementedError 스텁)
```

- **구현**: `stock`의 `StockAnalysisGateway`(질의 → 종목 코드 해석 → 유스케이스 위임) →
  stock CLAUDE.
- **소비**: `chat`의 `ChatInteractor`가 의도 분류(phase0)에서 주식 질문일 때 호출.
- **배선**: `main.py`에서 `app.dependency_overrides[get_stock_analysis_port] = get_stock_analysis_gateway`.

## 인바운드 라우터 규칙 — 유스케이스 슬라이스당 1개

라우터는 **HTTP 표면이 있는 유스케이스(수직 슬라이스)당 1개**다(스포크와 동일한 1:1 컨벤션).
단, HTTP 표면이 없는 포트/DTO 계약(스포크가 프로세스 안 DI로 쓰는 앱 간 계약)에는 라우터를
만들지 않는다 — 아무도 안 쓰는 공개 API·스켈레톤 라우터 금지(Simplicity First).

| prefix | 라우터 (슬라이스) |
|--------|------------------|
| /automation/* | `news_ingest` · `market_news_ingest` · `price_bar_ingest` · `news_label_ingest` · `fundamental_ingest` · `forecast_snapshot`(캡처·채점) · `mail_ingest` · `signal_scan` · `stock_demand`(수요 조회) · `dispatcher`(/myself) — 웹훅 토큰 공용 의존성은 `v1/webhook_token.py` |
| /email/* | `email_request` · `postmaster`(/myself) |
| /semantic/* · /langchain-semantic/* | `semantic`(ROM 1.0 — 단발 질의) · `langchain_semantic`(ROM 2.0 — 세션 멀티턴, LCEL 체인). 분류기(`SemanticLlmPort`)는 공유하고 답변 생성만 갈린다 — 계약이 달라(세션 id) 라우터를 나눴다 |
| /vision/* | `vision`(/myself·/images) · `face_recognition`(/faces) · `image_classifier`(/classifications) |

## 허브 소유 인프라 (adapter/outbound) — 예약

`adapter/outbound/`는 **허브 자신이 소유하는 전역 인프라** 접속 전용이다(star_craft 파이프라인
방향). 스포크 도메인 접속은 여기 두지 않는다 — 스포크 게이트웨이가 허브 포트를 구현한다.
현재: 비전 어댑터(`s3_vision_storage_adapter` · `log_vision_record_adapter` ·
`resource_adapters/yolo/` · `resource_adapters/convnext/`) ·
랭체인 엔진 어댑터(`langchain_chat_engine_adapter` — LCEL 체인, 아래 참고) ·
`orm/`·`mappers/`·`pg/`(랭체인 대화 세션 — 아래 ORM 예외).
도입 예정: `graph/`(Neo4j — 온톨로지 엔티티·관계, compose에 서비스 준비됨.
도입 조건·모델링 규칙 → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]]) ·
`vector/`(pgvector 재사용 또는 Qdrant — 전역 임베딩 검색).

### ORM 예외 — 랭체인 대화 세션 (2026-07-28)

허브는 원칙적으로 ORM/DB를 갖지 않지만, **랭체인 게이트웨이(ROM 2.0)의 대화 세션은 예외**다
(`langchain_sessions` · `langchain_turns`, alembic `d7e8f9a0b1c2`). 이 이력은 앱 간 협력 계약이
아니라 허브가 직접 소유·구현하는 기능의 상태라 위임할 스포크가 없다 — 비전이 허브 소유 기능인
것과 같은 성격이다. chat 스포크의 `conversations`와 합치지 않은 이유는 소유 앱이 다르고(허브
격리), 턴마다 시멘틱 분류 결과(`destination`)를 함께 남기기 때문이다.
**이 예외를 다른 슬라이스로 넓히지 않는다** — 새 협력은 여전히 포트로 스포크에 위임한다.

## 허브 소유 기능 — 랭체인 시멘틱 게이트웨이 (ROM 2.0)

시멘틱 의도 분류 뒤 **랭체인 LCEL 체인**으로 답하는 멀티턴 대화 창구. ROM 1.0(`semantic`)은
단발 질의로 그대로 남아 있고, 프론트 입력창의 ROM 1.0/2.0 셀렉터가 둘을 고른다.
랭체인 도입 경계·게이트 답안 → [[minseok/apps/admin/_docs/langchain-harness|langchain-harness]].

```
apps/hub/
├── adapter/inbound/api/{schemas,v1}/langchain_semantic_{schema,router}.py  # /langchain-semantic/myself·/ask
├── app/dtos/langchain_semantic_dto.py            # Ask·Response + EngineTurn·EngineAnswer
├── app/ports/input/langchain_semantic_use_case.py
├── app/ports/output/langchain_chat_engine_port.py    # 체인 실행(랭체인은 계약에 안 새어나온다)
├── app/ports/output/langchain_session_repository.py  # 세션·턴 영속 (이 슬라이스의 기록 포트 겸함)
├── app/use_cases/langchain_semantic_interactor.py    # 분류 → 근거 수집 → 체인 → 영속
├── adapter/outbound/langchain_chat_engine_adapter.py # ExaoneChatModel + rag/chat 체인 2벌
├── adapter/outbound/{orm,mappers,pg}/langchain_session_*.py
├── domain/langchain_chat/session_entity.py
└── dependencies/langchain_semantic_provider.py
```

- **분류기 공유**: `SemanticLlmPort`(ExaoneSemanticAdapter)를 ROM 1.0과 그대로 공유한다 —
  두 버전이 같은 의도 판정을 쓰고, 답변 생성 단계만 갈린다.
- **랭체인의 지분은 한 칸**: 프롬프트 조립(이력 주입)·출력 파싱뿐이다. 분기·가드레일
  (crud 미실행, rag 근거 없으면 답변 거부)은 인터랙터가 갖고, 모델 호출은
  `ExaoneChatModel`이 `llm_orchestrator`로 넘긴다(LLM 수렴 규칙 유지 — ChatOllama 미사용).
- **`langchain*` import는 `langchain_chat_engine_adapter.py` 한 파일뿐**이며,
  import-linter 프레임워크 격리 계약이 app·domain 유입을 막는다.

## 허브 소유 기능 — 비전 (YOLO)

이미지 분석·얼굴 탐지 파인튜닝. 앱 간 협력 계약이 아니라 **허브가 직접 구현·소유하는 기능**이다
(구 vision 스포크 흡수). YOLO 관련 코드(`FaceTrainingInteractor`, `resources/yolo_train` 데이터셋)를
읽거나 수정할 때는 [[minseok/apps/hub/_docs/YOLO_RESEARCH|YOLO_RESEARCH]]를 먼저 읽는다.

```
apps/hub/
├── adapter/inbound/api/v1/{vision,face_recognition}_router.py   # /vision/myself·/images · /vision/faces
├── app/ports/input/{vision,face_recognition,face_training}_use_case.py
├── app/ports/output/{vision_storage,vision_record,yolo,face_dataset}_port.py
├── app/use_cases/{vision,face_recognition,face_training,yolo}_interactor.py
├── adapter/outbound/                           # s3_vision_storage · log_vision_record · resource_adapters/yolo
├── dependencies/{vision,face_recognition,face_training}_provider.py
└── resources/yolo_train/                       # 파인튜닝 데이터셋
```

## 온톨로지 — 허브가 소유하는 전역 상위 개념

앱들이 공유하는 규범·어휘는 `hub/domain/`에 둔다(ragwatson star_craft의 온톨로지 역할).
현재: `domain/email/email_ontology.py` — 발신 이메일 작성 규범(EmailDirective)과
지시 합성(render_instruction, 순수 함수). `domain/navigation/tab_ontology.py` —
등급 게이팅 대상 탭 키 5종(`TAB_KEYS`: history·market·stock·vision·automation, 프론트
라벨·경로는 프론트 소유).

## 소유 계약 — EmailComposerPort

이메일 작성·발송 협력. 외부 요청(사용자/프론트)과 chat(구현: LLM 작성 + n8n 발송)을 잇는다.

```
POST /email/request → EmailRequestInteractor(온톨로지 지시 합성)
  → EmailComposerPort → chat EmailComposerN8nGateway(7.8B 작성 → n8n 웹훅 → Gmail)
```

- Gmail 자격증명은 n8n이 보유(백엔드 비밀 없음). 워크플로:
  [[minseok/apps/hub/_docs/n8n_email_sender_workflow.json]] (webhook path `redocean-email`).
- env: `N8N_EMAIL_WEBHOOK_URL` · `N8N_OUTBOUND_TOKEN`.

## 자동화 창구 — /automation (n8n 단일 접점)

외부 자동화(n8n)는 **허브만 안다**. 스포크는 n8n의 존재를 모른다(ragwatson star_craft 방식).
`X-Webhook-Token` 헤더로 검증한다(`N8N_INBOUND_TOKEN` env, 비면 검증 생략 — 로컬 개발).

```
apps/hub/
├── adapter/inbound/api/v1/{news_ingest,price_bar_ingest,news_label_ingest,fundamental_ingest,mail_ingest,signal_scan,dispatcher}_router.py   # /automation/* (공용 토큰: v1/webhook_token.py)
├── app/ports/input/{news_ingest,signal_scan}_use_case.py
├── app/use_cases/{news_ingest,signal_scan}_interactor.py
├── app/ports/output/news_storage_port.py          # 구현: stock NewsStorageGateway
├── app/ports/output/mail_storage_port.py          # 구현: mail MailStorageGateway
└── _docs/n8n_*_workflow.json                      # n8n에 임포트할 워크플로 2종
```

| 흐름 | 경로 |
|------|------|
| 뉴스 수집 | n8n(스케줄+RSS) → `POST /automation/news` → NewsIngestInteractor → `NewsStoragePort` → stock 저장 |
| 시그널 알림 | n8n(스케줄) → `POST /automation/stock-scan` → SignalScanInteractor → 기존 `StockAnalysisPort` 재사용 → n8n이 중립 제외 후 Gmail 발송 |
| 메일 수신 | n8n(Gmail Push/폴링) → `POST /automation/mail` → MailIngestInteractor → `MailStoragePort` → mail 저장(조회: `GET /mail/list`) |
| OHLCV 수집 | cron(`scripts/collect_prices.py`) → `POST /automation/prices` (+`GET /automation/prices/coverage`) → PriceBarIngestInteractor → `PriceBarStoragePort` → stock 저장 |
| 뉴스 라벨링 | cron(`scripts/label_news.py`, EXAONE 7.8B Ollama) → `GET /automation/news-labels/pending` → 라벨 → `POST /automation/news-labels` → NewsLabelIngestInteractor → `NewsLabelStoragePort` → stock 저장 |
| 상권 뉴스 수집 | cron(`scripts/collect_market_news.py`, 매일 01:30, Google News RSS "지역 어간 × 상권") → `POST /automation/market-news` → MarketNewsIngestInteractor → `MarketNewsStoragePort` → market 저장(+bge-m3 임베딩) |
| 펀더멘털 수집 | cron(`scripts/collect_fundamentals.py`, 주 1회, yfinance+DART) → `POST /automation/fundamentals` → FundamentalIngestInteractor → `FundamentalStoragePort` → stock 저장 |
| 예측 스냅샷 | cron(`scripts/snapshot_forecasts.py`, 매일 14:00) → `POST /automation/forecast-snapshots`(캡처) + `POST /automation/forecast-snapshots/score`(채점) → ForecastSnapshotInteractor → `ForecastSnapshotPort` → stock 저장·채점 |

- n8n 워크플로: [[minseok/apps/hub/_docs/n8n_news_collector_workflow.json]] ·
  [[minseok/apps/hub/_docs/n8n_stock_signal_alert_workflow.json]] — n8n UI에서 임포트,
  `REDOCEAN_WEBHOOK_TOKEN` env와 백엔드 URL(컨테이너 기준 `host.docker.internal:8000`)을 환경에 맞춘다.
- Gmail 수신 등 새 자동화도 같은 패턴: 허브 라우터에 엔드포인트 추가 → 허브 유스케이스 → 아웃바운드 포트.

## 소유 계약 — NewsStoragePort

뉴스 저장 협력. 허브 자동화(생성)와 stock(구현·영속: `news_articles` 테이블)을 잇는다.
stock 분석은 저장된 뉴스를 벤더 뉴스보다 우선 병합한다(한국 종목 뉴스 공백 해소).
`embed_missing(limit)`으로 미임베딩 뉴스 배치 임베딩(백필·재시도)도 위임한다 —
`POST /automation/news-embeddings/backfill`이 노출 창구.

## 소유 계약 — NewsSearchPort

뉴스 의미 검색 협력. chat(소비)과 stock(구현: bge-m3 임베딩 + pgvector 코사인,
`NewsSearchGateway`)을 잇는다. **계약은 자연어 질의 → NewsHit**(임베딩은 구현 스포크의
세부 — 모델 교체가 계약에 누설되지 않음). 히트에는 news_labels의 감성·이벤트 라벨이 동반된다.
검색 불가(임베딩 미가용)면 빈 리스트(열화 동작). ticker 인자로 종목 범위 제한, None이면 코퍼스 횡단.

## 소유 계약 — MarketNewsStoragePort · MarketNewsSearchPort

상권 뉴스 협력(주식 뉴스와 별개 코퍼스 — 조인 키가 ticker가 아니라 지역 어간 `area_tag`).
저장: 수집 배치(`collect_market_news.py`, 일 1회)와 market(구현·영속: `market_news_articles`,
적재 시 bge-m3 임베딩 동반)을 잇는다. 검색: chat(소비 — 상권 답변의 지역 기사 근거)과
market(구현: pgvector 코사인, `MarketNewsSearchGateway`)을 잇는다. 검색 불가 시 빈 리스트(열화 동작).

## 소유 계약 — NewsLabelStoragePort

뉴스 LLM 라벨 저장 협력. 라벨링 배치(`scripts/label_news.py`, EXAONE 7.8B Ollama —
도메인 내부 추론 계층)와 stock(구현·영속: `news_labels` 테이블, (news_id, labeler) 유니크)을
잇는다. `unlabeled()`가 라벨러별 미라벨 뉴스를 내줘 배치가 작업 큐로 쓴다. 라벨은 학습 피처 —
정답은 실현 수익률(`price_bars` 조인). labeler 버전 컬럼으로 상위 모델 재라벨링이 공존한다.

## 소유 계약 — FundamentalStoragePort

펀더멘털 스냅샷 저장 협력. 수집 배치(`scripts/collect_fundamentals.py`, yfinance + DART 무료 API,
주 1회)와 stock(구현·영속: `fundamental_snapshots` 테이블, (ticker, as_of, source) 유니크)을 잇는다.
PER/PBR/ROE/부채비율/FCF/EPS/BPS — 가격 파생(기술적) 축과 별개인 기업 가치·체력 축.
한국 종목은 yfinance가 PER/PBR/EPS를 안 줘 DART 재무제표로 자체 계산해 별도 행(source=dart)으로 공존.

## 소유 계약 — StockDemandPort

분석 질문 수요 조회 협력. 워치리스트 수요 편입 스크립트(`scripts/screen_us_undervalued.py`,
소비 — `GET /automation/stock-demand` 경유)와 stock(구현·영속: `stock_demand` 테이블,
`StockInteractor`가 분석마다 upsert 기록)을 잇는다.

```
apps/hub/app/
├── ports/output/stock_demand_port.py   # StockDemandPort (ABC) — top_demands(days, limit)
└── dtos/stock_demand_dto.py            # StockDemandRow(ticker·ask_count·last_asked_at)
apps/hub/dependencies/stock_demand_provider.py  # get_stock_demand_port (NotImplementedError 스텁)
```

- **구현**: `stock`의 `StockDemandGateway`(질문 수·최근성 순 조회).
- **배선**: `main.py`에서 `app.dependency_overrides[get_stock_demand_port] = get_stock_demand_gateway`.

## 소유 계약 — PriceBarStoragePort

OHLCV 봉 저장 협력. 수집기(`scripts/collect_prices.py`, 뉴스와 워치리스트 공유)와
stock(구현·영속: `price_bars` 테이블, (ticker, timeframe, ts) 유니크)을 잇는다.
`coverage()`가 (ticker, timeframe)별 보유 구간을 알려줘 수집기가 백필 깊이를 정한다 —
뉴스↔주가 반응 라벨링용(5m 단기 반응 · 1d 익일/주간). 소비자는 수집기 하나다 —
어드민 데이터소스 화면의 주가 봉 카드는 `StockDatasetStatsPort`가 준다(아래 참고).

## 소유 계약 — StockDatasetStatsPort

stock 소유 데이터셋의 적재 현황 조회 협력(조회 전용 — 저장은 각 StoragePort가 맡는
Record ↔ Directory 분리 선례). admin(소비)과 stock(구현)을 잇는다.
`get_dataset_stats()`가 뉴스·라벨·펀더멘털·예측 스냅샷·주가 봉 5종의 행수와
**최신 적재 시각(`created_at`)**을 준다 — `CommercialDataPort.get_dataset_stats`와
시그니처·DTO(`DatasetStat`)가 같아 admin은 두 목록을 이어붙이기만 한다.

기준 시각이 `created_at`인 것이 계약의 핵심이다. 봉 시각(`price_bars.ts`)·예측 기준일
(`forecast_snapshots.as_of`)·기사 발행일(`published_at`)은 도메인 시각이라 **수집이 멈춰도
최신으로 보인다** — 2026-07-25 수집 2일 정지를 아무도 감지하지 못한 원인이다.
신선도 판정 자체는 허브가 하지 않는다(운영 정책 = admin 도메인 서비스 `dataset_freshness`).

- **구현**: `stock`의 `StockDatasetStatsGateway`(5테이블 count + max(created_at)).
- **배선**: `main.py`에서 `app.dependency_overrides[get_stock_dataset_stats_port] = get_stock_dataset_stats_gateway`.

## 소유 계약 — ForecastSnapshotPort

예측 스냅샷 협력. 캡처 배치(`scripts/snapshot_forecasts.py`, 매일 14:00)·admin(소비)과
stock(구현·영속: `forecast_snapshots` 테이블, (ticker, horizon_days, as_of) 유니크)을 잇는다.
`capture(tickers, horizons)`(forecast+신호 분해 동결) · `score()`(horizon 도래분을 price_bars
실현 수익률로 채점 — UP→상승, DOWN→비상승, NEUTRAL은 NULL) · `accuracy_report(horizon,
recent_limit)`(적중률 요약+신호별 일치율+최근 목록 — admin analytics가 소비,
PriceBarStoragePort.coverage()를 admin이 같이 소비하는 선례와 동일).

## 소유 계약 — NewsEventStudyPort

뉴스 이벤트 사후 수익률 연구 리포트 조회 협력(조회 전용 — 쓰기는 `scripts/study_news_events.py`가
DB 직접, `AreaBacktestReportPort`와 같은 선례). admin(소비)과 stock(구현·영속:
`news_event_study_reports`, 실행당 1행 payload JSONB)을 잇는다. `latest()`가 최신 1건(없으면 None).

이 문서가 오래 *"라벨은 피처, 정답은 실현 수익률(price_bars 조인)"*이라 선언해두고 구현이
없었다 — 2026-07-27에 처음 구현됐다. 집계 스키마의 단일 정의처는
`stock/domain/services/event_study.py`.

**`excess_pct`가 본체다.** 절대 수익률은 표본 기간의 시장 방향을 그대로 반영한다 — 실측에서
7개 이벤트 유형이 전부 음수로 나오는데 이는 이벤트 효과가 아니다. 기준선(전체 평균)을 뺀
초과분으로 읽어야 한다. 리포트는 표본 집중도(`top_week_share`)와 경고도 함께 낸다.
**사용자 화면에 노출하지 않는다** — 어드민 전용(투자 정보가 아니라 라벨러 평가 연구).

## 소유 계약 — QuestionInsightPort

질문 인텔리전스 협력(조회 전용 — 쓰기는 chat의 대화 저장 경로가 이미 한다,
Record ↔ Directory 분리 선례). admin(소비)과 chat(구현·영속: conversations/messages)을 잇는다.
`recent_questions(limit)`(최근 질문 + 답변 종류) · `stats(days)`(총량·종류 분포·서울 외 지역 수요).

답변 종류는 저장값이 아니라 **관측 유도값**이다 — assistant payload 키(recommendations/stock/
news)와 서울 외 가드 고정 접두(`NONSEOUL_GUARD_PREFIX`, chat 인터랙터가 정의)로 판정한다.
서울 외 지역 카운트는 가드가 실제 차단한 질문 기준 — 전국 확장 우선순위의 실수요 신호.
계약에 개인 식별 정보(user_id·이메일)를 싣지 않는다.

- **구현**: `chat`의 `QuestionInsightGateway`(messages 읽기 전용 집계).
- **소비**: `admin`의 question_insight 인터랙터(`GET /admin/questions`).
- **배선**: `main.py`에서 `app.dependency_overrides[get_question_insight_port] = get_question_insight_gateway`.

## 소유 계약 — AreaBacktestReportPort

상권 점수 백테스트 리포트 조회 협력(조회 전용 — 쓰기는 `scripts/backtest_area_score.py`가
DB 직접, ingest 선례). admin(소비)과 market(구현·영속: `area_score_backtest_reports`,
실행당 1행 payload JSONB — 스키마 정의처는 market `area_score_backtester`)을 잇는다.
`latest()`가 최신 실행 리포트 1건을 반환(없으면 None).

## 규칙

새 앱 간 협력이 생기면, 스포크끼리 직접 잇지 말고 여기에 포트/DTO를 추가한 뒤 허브를 경유한다.
전체 토폴로지 → harness 문서(`_docs/harness.md`).
