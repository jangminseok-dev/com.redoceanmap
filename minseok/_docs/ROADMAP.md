# ROADMAP — 단계적 고도화 (2026-07-13)

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]] · 구조 강제 → [[_docs/harness|harness]]

목표는 **단계적**: ① 개인 투자/분석 도구 → ② 취업 포트폴리오 품질 → ③ 실사용자 서비스.
제약: 개발 단계 비용 0원(무료 리소스만) · 헥사고날/클린/DDD+SOLID 무조건 준수(import-linter
계약 5종) · 배포는 우분투 백엔드 PC가 `window` 브랜치 pull.

---

## Phase ① 개인 투자/분석 도구 완성 (~20-26일)

| # | 마일스톤 | 위치 | 기간 | 검증 |
|---|---------|------|------|------|
| M1 | **인증 가드 전면 적용 + 리프레시 토큰** — 전 라우터 JWT Depends(공개 화이트리스트 방식), 검증 의존성은 core/허브 포트 경유(스포크→auth import 금지) | auth 확장 + main.py 주입 | 2-3일 | 미인증 401 전수, 갱신 플로우 테스트 |
| M2 | ~~stock 피처 확장 + 백테스트 재채점~~ — **완료(2026-07-13~14)**. 2차(ATR·%B·거래량비·OBV) + 3차(12-1 모멘텀·거래량 확인 필터) 재채점. RSI+BB+MOM ±0.35 UP이 최우수 검증 신호(인샘플 하한 +3.5%p·홀드아웃 +0.9%p). 확률 제시는 계속 보류 → [[minseok/apps/stock/_docs/BACKTEST_RESCORE_2026-07\|RESCORE]] | stock 내부 | - | ✅ 성적표 문서화 |
| M3 | ~~market 시계열·스코어링 v1~~ — **완료(2026-07-15)**. `area_score` 수직 슬라이스: `GET /market/trdar/{code}/score` = 분기 추이(전 업종 합계 매출·유동인구 QoQ) + 시도 벤치마크 대비 종합점수(매출 성장·유동인구 성장·개폐업 건강도·영업 지속성 4컴포넌트, 순수 도메인 서비스 `area_scorer.py`) → [[minseok/apps/market/_docs/CLAUDE\|market CLAUDE]] | market 내부 (새 스포크 아님) | - | ✅ 스코어러 단위 테스트 18종 + 인터랙터 5종 (market 30 passed) + 실 DB 검증 |
| M4 | **뉴스 수집 상시화** — `scripts/collect_news.py`를 우분투 PC cron/systemd timer 등록, 실패 로그 | scripts/ + 운영 설정 | 2-3일 | 7일 연속 무중단 수집 |
| M5 | ~~chat 실데이터 결합 (핵심 가치)~~ — **완료(종목 2026-07-14 · 상권 2026-07-15)**. 종목: 지표 9종 의미 해석 + 검증 참고 신호 + 뉴스 RAG(bge-m3·pgvector, 허브 NewsSearchPort) 주입, phase0 3분류(stock/market_news/market). 상권: 허브 `get_area_scores`(M3 스코어링 재사용)로 phase2에 서울 평균 대비 종합점수 근거 주입 | chat 확장 | - | ✅ 테스트 15종+ / E2E 3/3, 상권 근거는 스텁 검증 + 게이트웨이 실 DB 검증 |
| M6 | ~~프론트-백엔드 정합~~ — **구현 완료(2026-07-15)**. ① vision `faces`로 통일(프론트 페이지·BFF·내비를 백엔드 도메인어에 맞춤, 실체가 얼굴 인식이므로), ② `fetchMarketAreas` dead code 삭제 + M3 스코어 API 프론트 연결(`AreaScoreCard`, 자료 패널), ③ 채팅 종목 카드에 신규 6필드 지표 그리드·검증 신호 배지·감성 노출, ④ market_news 뉴스 근거 카드 신설(백엔드 `AskResponse.news`+payload 저장 → 프론트 렌더·히스토리 복원) | www + 라우터 | - | ✅ 백엔드 159 테스트(신규 2)·계약 5 KEPT·tsc 0 에러·페이지 컴파일 전수 200. **배포 후 로그인→대화→지도→종목분석 수동 전 구간 통과 남음** |

## Phase ② 취업 포트폴리오 품질 (~15-20일)

| # | 마일스톤 | 기간 | 핵심 |
|---|---------|------|------|
| M1 | ~~GitHub Actions CI~~ — **취소(사용자 결정, 2026-07-13)**. 구축·첫 실행 통과까지 확인 후 제거. 검증은 로컬 수동(pytest + lint-imports) 유지 | - | - |
| M2 | **프로덕션 compose + deploy.sh** — --reload 제거, 비밀 .env 분리, healthcheck, DB 비노출. **n8n·neo4j prod 제외**(미사용). 배포=`git pull origin window && compose up -d --build` | 2-3일 | 우분투 PC 1커맨드 기동, 재부팅 자동 복구 |
| M3 | **백업** — pg_dump 일간(7세대) + rclone→Google Drive 15GB 무료(주간 4세대) + models/ 포함 | 1일 | 복원 리허설 1회 성공 |
| M4 | **RBAC + admin 스포크 실구현(최소)** — role 2종(free/admin)만, 실데이터 있는 화면만(회원/역할, 자동화 로그, 수집 현황). 목데이터 admin 페이지는 삭제. 데이터 접근은 허브 포트+DTO 경유 | 5-7일 | 역할별 접근 매트릭스 테스트 |
| M5 | **n8n 완전 탈피 + 프론트 ESLint** — 이메일 발송을 SMTP outbound adapter로 교체(포트 유지 — 어댑터 교체 사례), compose에서 n8n 제거 | 3-4일 | 이메일 E2E, n8n 컨테이너 0 |
| M6 | **문서 정합** — www/PLAN.md·README 현행화, 아키텍처 결정 기록(백테스트 기각 이력 포함), soccer·judge 스켈레톤 삭제 | 2-3일 | 문서-코드 전수 일치 |

### 편입 마일스톤 (2026-07-13 추가)

| 마일스톤 | 기간 | 핵심 |
|---------|------|------|
| ~~**market 전용 DB 런타임 전환**~~ ✅ **2026-07-22 완료** — ① core 앱별 세션(`MARKET_DATABASE_URL` 폴백형, `get_market_db`) ② market 프로바이더 8종 라우팅 ③ 데이터 이관(16테이블 60만+ 행, pg_dump --data-only --disable-triggers 원자 파이프 + pg_depend setval, 행수·임베딩 전수 대조) ④ 루트 체인 동결(env.py market ORM 제거 + include_name 필터 — 메인 사본 drop 시 필터도 제거). 독립 체인에 8d6efce2a41b(news·backtest 테이블) 추가, 백업에 market-*.dump 계층 추가. 메인 DB의 market 테이블 사본은 롤백 안전용으로 당분간 보존(후속: 사본 drop + 필터 제거) | 3-5일 | 완료 |

## Phase ③ 실사용자 서비스 (~20-30일, 수요 검증 가변)

| # | 마일스톤 | 기간 | 핵심 |
|---|---------|------|------|
| M1 | **공개 접점** — Cloudflare Tunnel(무료, 고정IP 불요) + HTTPS + rate limit(slowapi) | 2-3일 | 외부망 HTTPS 접속, 무차별 로그인 차단 |
| M2 | **북마크/관심종목** — recommendation 확장(새 스포크 아님) + 마이페이지 | 3-4일 | 등록→조회→삭제 E2E |
| M3 | **알림 v1(이메일)** — 관심 종목 신호 발생 시 발송. hub signal_scan_interactor 확장(교차 도메인 = 허브의 존재 이유) | 3-5일 | 신호→메일 수신 E2E |
| M4 | **운영 관측** — JSON 구조화 로깅 + Uptime Kuma(무료 self-host) + 장애 알림 | 2-3일 | 강제 다운 시 5분 내 알림 |
| M5 | **데이터 갱신 자동화 + LLM 라이선스 정리** — 상권 신규 분기 자동 적재, **EXAONE 라이선스 실사(연구용 한정 가능성 → 상용 전 Apache-2.0 계열 교체 검토)**. 교체 지점은 `core/llm/llm_orchestrator.py`로 국소화됨 | 4-6일 | chat 품질 회귀 10문항 비교 |
| M6 | **listing 스포크** — 실수요 확인 게이트 통과 시에만 | 6-8일 | 수요 게이트 통과가 착수 조건 |

---

## 새 도메인(스포크) 판정

| 후보 | 판정 | 근거 |
|------|------|------|
| 북마크/관심종목 | recommendation **확장** | "추천 기록"과 "찜"은 동일한 사용자↔분석대상 연결. CRUD 2-3개짜리 새 스포크는 과설계 |
| 알림 | hub **확장** (③ 후반 승격 재검토) | 조건 감시+발송은 교차 도메인 오케스트레이션 = 허브의 정의. 채널 다변화·구독 설정이 생기면 승격 |
| 시계열/스코어링 | market **내부** | 동일 애그리거트(상권)·동일 언어. 분리하면 스포크 간 데이터 왕복만 발생 |
| admin | 스포크 **실구현 완료** (2026-07) | 라우터 25개(`/admin/*`)·유스케이스 11종·프론트 9페이지. 권한은 엔드포인트 단 `require_permission`이며 `tests/test_admin_access_matrix.py`가 가드 누락·코드 오타·read권한 쓰기를 고정한다 |
| listing(매물) | ③에서 **새 스포크**, 수요 게이트 뒤 | 공공데이터 읽기(market)와 사용자 생성 쓰기(listing)는 액터·라이프사이클 상이 |
| game(모의투자·상권 창업) | **새 스포크** (2026-07-31) | listing과 동일 논리 — 유저 진행상태(쓰기)는 공공데이터 스포크(market·stock)와 액터·라이프사이클이 다르다. 게다가 **두 도메인을 지갑 하나로 가로질러** market·stock 어느 쪽에도 넣을 수 없다(넣으면 스포크 간 직접 참조가 필요해진다). 상권 데이터는 허브 신규 포트 1개로 읽기 전용 소비. 경계·게이트 → [[minseok/apps/game/_docs/game-harness\|game-harness]], 도입 순서 → [[minseok/apps/game/_docs/game-strategy\|game-strategy]] |
| 학습 파이프라인 | **앱 아님** — scripts/ 유지 | 오프라인 배치. 모델은 `models/<이름>/v<n>/`+지표 JSON+git 태그. MLflow/DVC 금지 |
| soccer | **삭제됨 (2026-07-15)** | 스켈레톤 금지 원칙. 코드·DB 컨테이너(:5433)·볼륨 제거, git 이력으로 복원 가능 |
| mail judge | **삭제 예정** (②-M6) | 스켈레톤 금지 원칙. git 이력으로 복원 가능 |

## 데이터·모델 트랙

- 뉴스 감성 피처의 백테스트 투입은 **약 3개월 축적 후** (표본 기준 미달 전엔 확률 주장 금지, 참고 정보로만)
- 피처 재채점 리포트를 `_docs`에 남겨 가설-검증-기각 서사로 활용
- 자체 모델 경로: 유해분류 v1(완료) → v2(운영 오탐 반영) → 뉴스 감성 한국어 경량 모델(KcELECTRA 파인튜닝). 자체 LLM 사전학습은 금지
- ~~후보: 상권 뉴스 수집 + RAG~~ — **구현 완료(2026-07-15)**. 수집원 조사 결과 별도 지역지
  RSS 불요: 기존 Google News RSS에 "지역 어간 × 상권" 키워드로 충분(dry-run 검증 — 지역별
  최신 기사 정확 매칭, 단 추상 키워드는 옛 기사 위주라 부적합). 주식 뉴스 패턴 복제:
  `collect_market_news.py`(일 1회) → 허브 `/automation/market-news` → market
  `market_news_articles`(+bge-m3) → `MarketNewsSearchPort` → chat 상권 답변 기사 근거 주입
- **후보(2026-07-14 추가): 상권 데이터 축 확장 3종 (전부 무료 공공 API, ①-M3 이후 우선순위 순)**
  현재 분기 데이터의 3대 공백 = 시의성(1~2분기 지연)·비용 측면(임대료 부재)·선행 신호.
  1. **행안부 인허가 데이터(localdata.go.kr)** — 음식점 등 인허가/휴폐업 **일 단위** 갱신.
     분기 지연 없는 개폐업 선행 신호(상권판 '봉 데이터'). 기존 수집 cron 패턴 재사용. 최우선.
  2. **국토부 실거래가 API** — 상가 임대/매매. "매출 대비 임대 부담" = 상권판 밸류에이션 축.
  3. **서울 지하철 승하차(일 단위)** — 분기 유동인구의 고빈도 프록시.
  비공공(지도 리뷰·SNS 스크래핑)은 약관 리스크 대비 이득 부족으로 비추천.

## 명시적 비추천 (과설계 목록)

메시지 브로커·MSA 분리 / K8s·클라우드 /
MLflow·Airflow·DVC / 알림 스포크 선제 신설 / paid·결제 / SNS 로그인(껍데기 버튼 제거) /
admin 6페이지 전면 구현 / 커버리지 수치 목표 / GraphQL·BFF /
자동 배포 파이프라인(③까지 deploy.sh 수동 1커맨드)

**도입 예정으로 옮긴 항목** (2026-07-28) — 비추천 목록에서 뺐지만 무제한 승인은 아니다.
각 하네스의 게이트를 통과한 범위에서만 들어온다.

| 항목 | 상태 | 게이트 |
|---|---|---|
| 랭체인 | **도입됨** — `langchain-core` 1개, 허브 랭체인 게이트웨이(ROM 2.0) 1파일 | [[minseok/apps/admin/_docs/langchain-harness\|langchain-harness]] §5 (패키지 추가 시마다 재통과) |
| Neo4j 그래프DB | **도입 예정 · 시점 미정** — 아직 그래프 접속 코드 0건, `graph/` 선채우기 금지 유지 | [[minseok/apps/admin/_docs/neo4j-harness\|neo4j-harness]] §5-5 (그래프로만 답하는 질문·제약 Cypher·투영 경로·장애 격리) |
