# ROADMAP — 단계적 고도화 (2026-07-13)

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]] · 구조 강제 → [[_docs/harness|harness]]

목표는 **단계적**: ① 개인 투자/분석 도구 → ② 취업 포트폴리오 품질 → ③ 실사용자 서비스.
제약: 개발 단계 비용 0원(무료 리소스만) · 헥사고날/클린/DDD+SOLID 무조건 준수(import-linter
계약 5종) · 배포는 우분투 백엔드 PC가 `window` 브랜치 pull.

---

## Phase ① 개인 투자/분석 도구 완성 (~20-26일)

| # | 마일스톤 | 위치 | 기간 | 검증 |
|---|---------|------|------|------|
| M1 | ~~인증 가드 전면 적용 + 리프레시 토큰~~ — **완료(2026-07-13, 4921c4e)**. 전 라우터 JWT Depends(공개 화이트리스트), 리프레시 회전 | auth 확장 + main.py 주입 | - | ✅ 백엔드 PC 배포·E2E — 미인증 401 전수, 가입→Bearer 200→회전→재사용 401 |
| M2 | ~~stock 피처 확장 + 백테스트 재채점~~ — **완료(2026-07-13~14)**. 2차(ATR·%B·거래량비·OBV) + 3차(12-1 모멘텀·거래량 확인 필터) 재채점. RSI+BB+MOM ±0.35 UP이 최우수 검증 신호(인샘플 하한 +3.5%p·홀드아웃 +0.9%p). 확률 제시는 계속 보류 → [[minseok/apps/stock/_docs/BACKTEST_RESCORE_2026-07\|RESCORE]] | stock 내부 | - | ✅ 성적표 문서화 |
| M3 | ~~market 시계열·스코어링 v1~~ — **완료(2026-07-15)**. `area_score` 수직 슬라이스: `GET /market/trdar/{code}/score` = 분기 추이(전 업종 합계 매출·유동인구 QoQ) + 시도 벤치마크 대비 종합점수(매출 성장·유동인구 성장·개폐업 건강도·영업 지속성 4컴포넌트, 순수 도메인 서비스 `area_scorer.py`) → [[minseok/apps/market/_docs/CLAUDE\|market CLAUDE]] | market 내부 (새 스포크 아님) | - | ✅ 스코어러 단위 테스트 18종 + 인터랙터 5종 (market 30 passed) + 실 DB 검증 |
| M4 | ~~뉴스 수집 상시화~~ — **완료(2026-07-13, 51eba10)**. ticker 조인 키 + (url,ticker) 유니크, 1,182건 백필, 백엔드 PC cron 등록·가동 확인 후 상시 운영 중 | scripts/ + 운영 설정 | - | ✅ 가동 확인(2026-07-13) 후 3주+ 운영 |
| M5 | ~~chat 실데이터 결합 (핵심 가치)~~ — **완료(종목 2026-07-14 · 상권 2026-07-15)**. 종목: 지표 9종 의미 해석 + 검증 참고 신호 + 뉴스 RAG(bge-m3·pgvector, 허브 NewsSearchPort) 주입, phase0 3분류(stock/market_news/market). 상권: 허브 `get_area_scores`(M3 스코어링 재사용)로 phase2에 서울 평균 대비 종합점수 근거 주입 | chat 확장 | - | ✅ 테스트 15종+ / E2E 3/3, 상권 근거는 스텁 검증 + 게이트웨이 실 DB 검증 |
| M6 | ~~프론트-백엔드 정합~~ — **구현 완료(2026-07-15)**. ① vision `faces`로 통일(프론트 페이지·BFF·내비를 백엔드 도메인어에 맞춤, 실체가 얼굴 인식이므로), ② `fetchMarketAreas` dead code 삭제 + M3 스코어 API 프론트 연결(`AreaScoreCard`, 자료 패널), ③ 채팅 종목 카드에 신규 6필드 지표 그리드·검증 신호 배지·감성 노출, ④ market_news 뉴스 근거 카드 신설(백엔드 `AskResponse.news`+payload 저장 → 프론트 렌더·히스토리 복원) | www + 라우터 | - | ✅ 백엔드 159 테스트(신규 2)·계약 5 KEPT·tsc 0 에러·페이지 컴파일 전수 200. **배포 후 로그인→대화→지도→종목분석 수동 전 구간 통과 남음** |

## Phase ② 취업 포트폴리오 품질 (~15-20일)

| # | 마일스톤 | 기간 | 핵심 |
|---|---------|------|------|
| M1 | ~~GitHub Actions CI~~ — **취소(사용자 결정, 2026-07-13)**. 구축·첫 실행 통과까지 확인 후 제거. 검증은 로컬 수동(pytest + lint-imports) 유지 | - | - |
| M2 | ~~프로덕션 compose + deploy.sh~~ — **완료(2026-08-20 컷오버·검증)**. 전환 점검에서 초안의 결함 6건을 잡고 고쳤다: ① `cloudflared` 누락(공개 도메인 전면 중단) ② `extra_hosts` 누락(`host.docker.internal` 미해석 → Ollama·market DB 동시 단절) ③ `MARKET_DATABASE_URL`이 `localhost`(컨테이너가 자기 자신을 가리켜 **메인 DB로 조용한 폴백** — 2026-07-24 실장애 재현) → `MARKET_DATABASE_URL_DOCKER` 신설·주입 ④ 헬스체크가 `/openapi.json`(backend 401·auth 404 → 영구 unhealthy) → `/health` ⑤ `n8n` 중복 선언(별도 프로젝트가 5678·`n8n_data` 점유) 제거 ⑥ 프로젝트명 `comredoceanmap` 유도(컨테이너 개명 → cron `docker exec redoceanmap-backend-1` 파손) → `name: redoceanmap` 고정. `.env`에 `KAKAO_APP_ID` 누락도 함께 발견(모바일 카카오 로그인). 이미지 태그를 `minseok97/redoceanmap-backend:latest`로 명시 — 빼면 배치 cron 2종이 낡은 이미지를 돈다. **⛔ `--remove-orphans` 금지**(같은 프로젝트명의 dev neo4j가 삭제되어 그래프 투영 cron이 죽는다) | - | ✅ 8개 컨테이너 `unless-stopped`·backend·auth healthy·공개 도메인 200·market 폴백 False |
| M3 | **백업 — 부분 완료**. 일간 pg_dump 7세대 + 무결성 검증 + market 덤프 계층(`scripts/backup_db.sh`, 04:00 cron) 완료. **잔여**: rclone→Google Drive 오프사이트(스크립트 주석에 "후속 계층"으로 명시) + 복원 리허설 | 잔여 반나절 | 복원 리허설 1회 성공 |
| M4 | ~~RBAC + admin 스포크 실구현~~ — **완료(2026-07-21)**. RBAC 4테이블(auth 소유) + `require_permission`, admin 스포크는 허브 포트 소비, `grant_admin.py` 부트스트랩 | - | ✅ `tests/test_admin_access_matrix.py` — 가드 누락·코드 오타·read권한 쓰기 고정 |
| M5 | ~~n8n 완전 탈피 + 프론트 ESLint~~ — **취소(사용자 결정, 2026-08-04)**. n8n·이메일 경로 현행 유지, 재제안 금지 | - | - |
| M6 | ~~문서 정합~~ — **취소(사용자 결정, 2026-08-04)**. 루트 README는 2026-08-04 신규 작성됨, 나머지 항목(judge 스켈레톤 삭제 포함) 보류 | - | - |

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
| mail judge | **삭제 보류** (②-M6 취소, 2026-08-04) | 스켈레톤 금지 원칙은 유지되나 삭제를 담던 ②-M6가 취소됨. git 이력으로 복원 가능 |

## 데이터·모델 트랙

### 미사용 데이터 소진 계획 (2026-08-04 확정 — 감사 결과의 후속)

우선순위 순. 각 항목의 대기 사유가 곧 선행 조건이다.

| # | 항목 | 선행 조건 | 계획 |
|---|---|---|---|
| E1 | ~~**5분봉 이벤트 연구 확장**~~ — **완료(2026-08-20)**. `aggregate_intraday` + `study_news_events.py --minutes 30 60` → payload `short_horizon[]` → 허브 `ShortHorizonRow` → admin 화면. 첫 실측(5분봉 2026-04-16~, 표본 66,634): **30·60분 초과수익은 전 유형 ±0.13%p 이내로 사실상 없다.** 5일 지평의 "강한 부정 +2.32%p"와 대비되어, 값은 즉각 반응이 아니라 되돌림에서 나온다는 해석이 선다. 함정 1건 기록: q1을 `published_at + N분`에 걸면 장외 발행에서 q0·q1이 같은 봉이 되어 표본 75.1%가 수익률 0이 된다 — 기준은 **진입한 봉(q0.ts)**이다 |
| E0 | ~~**가중치 재적합·자동 승격 루프**~~ — **완료(2026-08-21)**. 예측 루프의 마지막 고리(채점 → 재적합 → 승격)를 닫았다. ①활성 판정 조합 DB화(`forecast_signal_configs`, 부분 유니크로 활성 1행 강제, 행 부재 시 코드 상수 폴백 — 조합 키가 forecast 캐시 키·스냅샷 `signal_config` 스탬프에 들어가 승격 즉시 반영·이력 분리) ②순수 도메인 `weight_refit.py`(동결 원신호 × 실현 수익률 재채점, 후보 32조합 명시 열거, 게이트 = n≥100 + Wilson 하한 > 기준선 + 현행 대비 마진 0.02 + 멱등, w_sentiment=0·하락 무발화 고정) ③`POST /automation/forecast-refit`(허브 `ForecastRefitPort`) + `scripts/refit_forecast_weights.py`(매주 토 15:00 cron 등록됨) ④admin `GET /admin/forecast-refit` + `/admin/forecast-refit` 화면(리더보드·조합 이력). 미달 리포트도 `forecast_refit_reports`에 저장 — 현재 표본(UP n=72<100)으로는 ~9월까지 미달 리포트만 쌓이는 것이 정상. 상세는 stock CLAUDE가 정본 | - | 도메인·인터랙터 테스트 신설, 계약 5 KEPT |
| E2 | **펀더멘털 → 판정 편입** (3-5일) | 분기 지평 백테스트 설계 | DART 연간·분기 보고서는 **과거 소급 수집이 가능**하다(뉴스와 다른 점) — 과거 펀더멘털 백필 → 60~120거래일 워크포워드(PER/PBR 분위 → t+지평 수익률 vs 기준선) → 통과 시 단기 방향과 **분리된 장기 가치 축**으로 노출(섞으면 지평이 다른 신호가 오염된다) |
| E3 | **뉴스 감성 피처 재채점** (실행 ~2026-10) | 라벨 3개월 축적(n≥100+Wilson) | 지금 할 준비: 백테스트 스크립트에 `--sentiment-from-labels` 투입 경로를 미리 구현해두고, 10월에 돌리기만 한다. 라벨 품질 사전 신호는 이벤트 연구(excess 기준)가 이미 제공 중 |
| E4 | **Neo4j 게이트 답안** (설계만, 코드 0) | neo4j-harness §5-5 통과 | 후보 실사: ⑴상권 다중 홉 유사도 — 속성 필터라 SQL로 가능, 탈락 ⑵종목-업종-뉴스 전이 — 1홉 조인, 탈락 ⑶**GraphRAG**(뉴스·상권 인사이트·PDF 요약을 엔티티-관계로 잇는 chat 근거 확장, star_craft 방향) — 유일한 진짜 그래프 우위 후보. ⑶의 게이트 답안 문서를 먼저 쓰고 통과 시에만 착수 |
| E5 | ~~**EXAONE 라이선스 실사**~~ — **완료(2026-08-17)**. EXAONE 3.5 = "EXAONE AI Model License Agreement 1.1 - NC" — **연구 전용, 상용 금지**(모델·파생물·**Output까지** 수익 창출 목적 사용 금지, 상용은 LG AI Research와 별도 계약). 결론: ①②단계(개인 도구·포트폴리오)는 비상용이라 현행 유지 가능, **③ 공개 서비스 전 교체 필수**(③-M5와 연동). 파인튜닝 투자 보류 유지(NC 파생물도 NC). 교체 후보(중국 모델·중국 베이스 파인튜닝 배제 제약 유지): Llama 3.x(커뮤니티 라이선스, 상용 가능)·Gemma 3(Gemma Terms, 상용 가능)·카카오 Kanana(Apache 2.0, 자체 베이스). SKT A.X는 Qwen 베이스라 배제. 교체 지점은 `core/llm/llm_orchestrator.py`로 국소화됨 |


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
  1. ~~행안부 인허가 데이터~~ — **완료(2026-07-30)**. 서울 열린데이터광장 LOCALDATA_072404/5로
     68만 건 수집·48.6% 상권 매칭, `permit_churn` 노출(→ market CLAUDE). chat 주입은 개선
     사이클 Phase B에서.
  2. **국토부 실거래가 API — 편입 확정(2026-08-04, 사용자 결정)**. 상가 임대/매매 →
     "매출 대비 임대 부담" 축. 상권 축의 유일한 경쟁 열세 지점(소상공인 상권정보는 임대
     시세 제공)을 메운다. 수집 스크립트 + market 팩트 테이블 + narrator 확장.
  3. **서울 지하철 승하차(일 단위)** — 후보 유지. 분기 유동인구의 고빈도 프록시.
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
