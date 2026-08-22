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

### R 트랙 — 검색(Retrieval) 품질 (2026-08-21 추가)

E 시리즈(데이터·모델 트랙)가 **투자 판정** 축이라면, R 트랙은 **RAG 검색 품질** 축이다.
현행 검색은 기사 **제목 한 줄**을 bge-m3로 임베딩한 순수 코사인 top-k이며, 청킹·키워드 채널·
리랭킹·검색 품질 지표가 전부 없다. 기존 평가 하네스(`apps/chat/tests/eval/`)는 *생성·의도분류*
품질만 재고 *검색* 품질은 재지 않는다 — R 트랙은 그 공백을 메운다.

현황 실측(2026-08-21): `news_articles` 73,257행(전부 임베딩, 공유 DB) ·
`market_news_articles` 2,077행(market DB) · 벡터 인덱스 없음(`a3b4c5d6e7f8`가 "10만 건 넘으면
hnsw 재검토"로 유예 — 73k라 곧 닿는다) · `pg_trgm` 사용 가능(미설치) ·
`pg_bigm`·`pgroonga` **없음**(한국어 형태소 분석기 부재).

| # | 마일스톤 | 선행 | 기간 | 게이트 |
|---|---------|------|------|--------|
| R1 | **검색 품질 계측 기반** — **하네스 완료(2026-08-23) · baseline은 라벨 대기**. 계획 ①~④ 전부 구현: ① 골든셋 `apps/chat/tests/eval/retrieval_golden.jsonl`(질의 40건 = stock 25 + market 15, labels 비움 — TREC pooling 후 사람이 0/1/2) ② 순수 채점기 `chat/domain/services/retrieval_scorer.py`(recall@5/10·nDCG@5/10·MRR·mAP, 지수 이득 2^g−1, pending·no_relevant는 평균 제외 — 산식 손계산 대조 테스트 5종) ③ 러너 **`minseok/tests/test_retrieval_runner.py`**(-m ollama — chat/tests가 아닌 합성 루트 위상에 둔 이유: stock·market 유스케이스를 함께 조립해야 해서 chat 안에서는 스포크 상호 독립 계약에 걸린다) → `retrieval_trace.jsonl`(랭킹) + `retrieval_pool.jsonl`(top-20 라벨링 시트) ④ 게이트 `test_retrieval_gate.py`(결정론 절대 규칙 + -0.03 회귀, baseline 부트스트랩·라벨 0건이면 skip). **잔여 절차**: ⑴ 백엔드 PC에서 러너 실행(파일 docstring의 docker 커맨드) ⑵ `retrieval_pool.jsonl`을 보고 **사람이** golden의 labels를 채움(⛔ LLM 라벨링 금지 — 7.8B가 자기 검색을 심판하는 순환) ⑶ 게이트 첫 실행이 `retrieval_baseline.json` 기록 → R2의 "+0.03" 기준점 | 없음 | 1.5-2일 | baseline 기록 + **같은 트레이스 재채점 시 동일 결과**(결정론 — 게이트 절대 규칙으로 구현됨) + 계약 5 KEPT ✅ |
| R2 | **하이브리드 검색(trigram + 벡터 RRF)** — **구현 완료(2026-08-23) · 판정은 라벨 뒤**. ① `pg_trgm` 마이그레이션 2종(공유 DB `j9c0d1e2f3a4` · market DB `d8e9f0a1b2c3` — title trigram GIN, trusted 확장) ② `search_hybrid`를 stock·market 두 PG 리포지토리에 **실험 경로로** 추가(⚠ 프로덕션 미전환 — 유스케이스는 현행 순수 코사인 유지, 게이트 통과 시에만 포트·유스케이스 전환). RRF는 앱별 순수 도메인 `rrf_fusion.py`(k=60, 동점은 문서 키 오름차순 결정론, 소형 복제 컨벤션) + 손계산 테스트 각 3종. 채널별 top-30, trigram 0점 행 제외, 채널 내·최종 제목 dedupe. 러너가 **두 시스템 트레이스 + pooling 합집합 시트**를 함께 생성(TREC pooling — 라벨 1회로 두 시스템 비교), `test_retrieval_hybrid_report.py`가 같은 라벨 표본 채점 후 nDCG@5 델타·판정을 출력(채택을 강제하지 않음 — 기각도 유효). **잔여**: 백엔드 PC `alembic upgrade`(compose 자동)+러너 실행 → 사람 라벨 → 판정. ③ 파라미터 스윕·④ 벡터 인덱스 latency 실측은 라벨 확정 뒤. **한계 명시**: 문자 trigram(형태소 아님). **범위 밖**: 리랭커(단일 모델 정책 예외 판정 선행) | **R1** | 2-3일 | R1의 **nDCG@5가 baseline 대비 +0.03 이상**. 미달이면 **기각하고 현행 순수 코사인 유지**(E2와 동일 처리) — 판정 재료는 hybrid report가 출력 |
| R3 | **청킹 전략(DART 공시 원문)** — **구현 완료(2026-08-23) · 판정은 라벨 뒤**. **착수 전 확인 통과**: 삼성전자 사업보고서(20260310002820) 실측 — ZIP 안 XML(UTF-8), 표는 완전한 마크업(`TABLE` 2,071·이미지 2뿐). 단 well-formed가 아니라(이스케이프 안 된 `&`·장식용 `<`) 전처리로 살린다. **각주의 실제 위치도 실측으로 확정**: 전용 태그가 없고 ⑴ 표 안의 `※` 행 ⑵ 데이터 표 **다음의 한 줄짜리 안내 표**(103건 — 직전 표에 승계) ⑶ 드물게 직후 P. `(주)회사명`을 각주로 오분류하는 함정을 잡았다(계열사 목록 801행이 각주로 흡수됐던 버그). ① `scripts/collect_disclosures.py`(한국 10사 × 최신 사업보고서, corp 코드 캐시 재사용, (rcept_no, strategy) 교체 멱등, `--embed` 배치) ② `disclosure_chunks`(루트 체인 `k0d1e2f3a4b5`, **strategy 컬럼 추가** — 3전략 병렬 저장이 비교의 축) ③ 청킹 3종: 순수 도메인 `disclosure_chunker.py` — (a) 고정 512자/오버랩 64(토크나이저 미보유 — 문자 근사 명시) (b) 섹션 병합(상한 2,000자 초과 재분할) (c) 표 행 단위 + 섹션·캡션·**헤더=값 페어링** + 각주 인라인(행 상한 1,000자 — 실측 최대 2.3만 자 병합 셀 방어). 실물 검증: 요소 1,683(표 1,093)·전략별 청크 1.7k/1.7k/9.0k ④ 공시 골든셋 20건(`retrieval_golden_disclosure.jsonl` — 표 질의 12·서술 8, 카테고리로 구분) + 전략별 러너(`test_retrieval_disclosure_runner.py`) + 비교 리포트(`test_retrieval_chunking_report.py` — 게이트 판정 출력, 채택 비강제). 파서·청커 테스트 8종. **잔여**: 백엔드 PC 적재+임베딩(≈수십 분)·러너·사람 라벨·판정 | **R1** (R2와 병행 가능) | 3-4일 | (c)가 (a) 대비 **표 질의 `recall@5` +0.10 이상**. 미달이면 청킹 고도화 기각, (a) 고정 토큰 유지 — 판정 재료는 chunking report가 출력 |
| R4 | **문장 단위 출처 인용** — **완료(2026-08-23)**. ① `stock_answer`·`market_news_answer` 컨텍스트에 `근거 [n]` 번호 부여(단일 정의처는 chat_interactor — stock은 고정 배정 [1] 시세·지표 / [2] 과거 통계 / [3] 가치·체력 / [4] 감성·헤드라인 / [5]+ 관련 뉴스 개별, 블록 없으면 결번) + 프롬프트가 수치·사실 문장 말미 `[n]` 마커 의무화(고지 문장 제외) ② `eval_scorer`에 `citation_coverage`(수치 문장 중 마커 비율 — 마커가 마침표 뒤로 밀린 표기도 앞 문장 귀속) + `dangling_citation`(컨텍스트에 없는 번호 인용 — **절대 규칙 즉시 발효**, 구 트레이스는 마커가 없어 자연 통과) ③ 프론트 ChatPanel이 `[n]`을 근거 배지로 렌더, 근거 뉴스 목록에 같은 번호 병기(본문↔카드 대응). **`PHASE2_PROMPT`(market)는 제외 판정** — 기사 근거가 프론트 카드로 노출되지 않아 앵커가 성립하지 않고, JSON 스키마+마커 이중 요구는 7.8B 준수율 리스크(C2 선례 31%). 상권 기사 카드가 생기면 후속 | **R1** 불요 (독립) | 0.5일 | `dangling_citation` 0건 절대 규칙 ✅(scorer 테스트 3종 + 인터랙터 주입 테스트 2종) · `citation_coverage`는 회귀 키 등록 완료 — **다음 eval 실행(-m ollama) 때 baseline에 실측 편입**(없던 시절 baseline 자동 스킵 규칙) |

- **총 8-10일** (R1 → R2·R3 병행, R4는 언제든 독립 착수 가능).
- 산출물: `minseok/_docs/RETRIEVAL_EVAL_2026-08.md` — [[minseok/apps/stock/_docs/FUNDAMENTAL_BACKTEST_2026-08|FUNDAMENTAL_BACKTEST]] 패턴.
  **기각도 결과로 쓴다.**
- 착수 동기(2026-08-21): LLM & RAG 엔지니어 공고 대조에서 평가·운영 축(골든셋 120건 + 결정론
  지표 + baseline 회귀 게이트)은 정통으로 맞았으나 **검색 축(청킹·하이브리드·리랭킹·recall@k)이
  전부 비어 있음**이 확인되었다. R 트랙은 그 공백을 코드와 숫자로 메우는 최소 경로다.

**도달 수준 (마일스톤별 — 무엇을 말할 수 있게 되는가)**

| 시점 | 도달 수준 |
|---|---|
| 현재 | RAG를 **써 본** 수준. 임베딩·pgvector·프롬프트는 다루나 검색 품질을 물으면 코드로 답할 게 없다 |
| R1 (2일) | **투자 대비 효율의 정점.** "현행 검색의 nDCG@5를 골든셋 40건으로 고정하고 회귀 게이트를 걸었다"가 성립. 평가 하네스가 생성 축 + 검색 축 **양쪽**을 덮는다 |
| +R4 (3일) | 출처 인용이 "붙인다"에서 "**측정한다**"로 넘어간다. `dangling_citation` 절대 규칙은 환각 대응의 새 유형 |
| +R2 (6일) | "하이브리드로 nDCG@5를 X→Y로 올렸다" **또는 "게이트 미달로 기각하고 현행 유지"**. 후자도 동등하게 유효하다 — E2와 같은 서사이며, 측정해서 기각한 이력이 개선 주장보다 신뢰도가 높다 |
| +R3 (8-10일) | 표·각주 청킹을 대조군 포함 실험 설계로 설명 가능. RAG 파이프라인 전 구간을 자기 코드로 짚을 수 있다 |

**R 트랙을 다 해도 남는 공백** (숨기지 말고 먼저 인정할 것)

- **실서비스 규모 아님** — 73k 헤드라인 + 공시 10사는 "대규모 문서"가 아니다
- **리랭커 없음** — 단일 모델 정책 예외 판정 전까지 미도입. "정책상 미도입"은 설계 규율로 설명 가능하다
- **스캔 PDF·이미지 표 없음** — R3 게이트에서 이미지면 중단하기로 명시했다
- **1인 저장소** — 팀 협업·코드리뷰 이력 없음
- **경력 연수** — 코드로 메울 수 없는 항목이다

## Phase ③ 실사용자 서비스 (~20-30일, 수요 검증 가변)

| # | 마일스톤 | 기간 | 핵심 |
|---|---------|------|------|
| M1 | **공개 접점** — Cloudflare Tunnel(무료, 고정IP 불요) + HTTPS + rate limit(slowapi) | 2-3일 | 외부망 HTTPS 접속, 무차별 로그인 차단 |
| M2 | ~~**북마크/관심종목**~~ — **완료(2026-08-21)**. recommendation 확장: `bookmarks` 테이블(h7a8b9c0d1e2, (user, type, key) 유니크) + `/bookmarks` CRUD(재등록 멱등·종목 키 대문자 정규화·상한 200) + 프론트 `/bookmarks` 페이지·주식 히어로/상권 오버레이 토글 버튼(서버 목록 단일 진실). 상세는 recommendation CLAUDE 정본 | - | ✅ 등록→조회→삭제 E2E + 인터랙터 테스트 7종 |
| M3 | **알림 v1(이메일)** — **구현 완료(2026-08-23) · E2E 잔여**. 허브 새 슬라이스 `bookmark_alert`(signal_scan 확장 대신 1:1 슬라이스 신설 — 사용자별 북마크 알림은 계약이 다르다): n8n(매일 15:30, 스냅샷 cron 뒤) → `POST /automation/bookmark-alerts`(웹훅 토큰) → 북마크(허브 **BookmarkDirectoryPort 신설**, recommendation 구현) × 신호(M7의 `StockStatusPort` 재사용 — 메일과 보드가 같은 값) × 이메일(허브 **MemberContactPort 신설**, auth 구현 — 정지·탈퇴·무이메일 제외) 조합, **비중립만** 알림. 메일은 순수 도메인 `bookmark_alert_composer` 결정론 템플릿(LLM 미사용 — 권유 어휘 금지·책임 고지 필수·"일일 수집 기준" 명시, 회귀 테스트로 고정). 발송은 n8n Gmail(자격증명 백엔드 무보유 원칙 유지) — 워크플로 JSON 동봉, n8n UI 임포트 필요. 테스트 8종(조합·제외 4 + 컴포저 4). **잔여**: 백엔드 PC 배포 + n8n 워크플로 임포트 후 신호→메일 수신 E2E. v1 한계: 신호 유지 시 반복 발송(dedupe 후속) | 3-5일 | 신호→메일 수신 E2E |
| M4 | **운영 관측** — JSON 구조화 로깅 + Uptime Kuma(무료 self-host) + 장애 알림 | 2-3일 | 강제 다운 시 5분 내 알림 |
| M5 | **데이터 갱신 자동화 + LLM 라이선스 정리** — 상권 신규 분기 자동 적재, **EXAONE 라이선스 실사(연구용 한정 가능성 → 상용 전 Apache-2.0 계열 교체 검토)**. 교체 지점은 `core/llm/llm_orchestrator.py`로 국소화됨 | 4-6일 | chat 품질 회귀 10문항 비교 |
| M6 | **listing 스포크** — 실수요 확인 게이트 통과 시에만 | 6-8일 | 수요 게이트 통과가 착수 조건 |
| M6.5 | ~~**개인화 ⓪ — 투자·창업 프로파일**~~ (recommendation 확장) — **완료(2026-08-22)**. 자기신고 설문(목적·투자성향 5등급·예산 밴드·부채 부담·투자 기간)을 `user_profiles`(사용자당 1행, `i8b9c0d1e2f3`)에 저장하고, chat이 허브 `UserProfilePort` 경유로 stock·market 서술 컨텍스트에 라벨을 주입한다(미작성·실패는 주입 생략 — 무손상). **마이데이터·신용점수 연동은 로드맵에서 제외** — 본인신용정보관리업 허가(법인·자본금)와 유료 API가 필요해 무료 범위 원칙과 충돌. 정확 금액 대신 밴드만 받는다(개인 금융 정보 부담 최소화). 개인화는 **서술 관점 조정까지** — 프로파일 근거 매매 권유·예산 적합 단정은 프롬프트 규칙으로 금지(투자자문 경계, 기존 지시 금지 규칙 유지). 프론트 `/profile` 설문 페이지 | 1일 | 열화 3종(비로그인·미작성·조회 실패) 회귀 테스트로 고정 — 프로파일이 없어도 답변은 기존과 동일해야 한다. 효과 측정(정렬 개인화)은 M8과 함께 실사용자 게이트 뒤 |
| M7 | ~~**개인화 ① — 관심 목록 상태 보드**~~ (recommendation 확장) — **완료(2026-08-23)**. `/bookmarks`를 "내 관심 대상의 지금"으로 승격: `GET /bookmarks/board`가 종목엔 방향·전일 대비·검증 참고 여부(허브 **`StockStatusPort` 신설** — stock이 동결 스냅샷+최근 종가 2봉만 읽는 `StockStatusGateway`로 구현, 심볼마다 analyze 호출 배제·접미 변형 흡수·10일 초과 스냅샷 제외), 상권엔 종합점수·등급·전분기 대비 매출 QoQ(기존 `CommercialDataPort.get_area_scores` 재사용)를 붙인다. 새 수집·모델·테이블 없음(계획대로 조합만 — 단 기존 포트 재사용 대신 스냅샷 일괄 조회용 허브 포트 1개는 신설). 격리는 조회 범위 자체(`find_by_user`)로 보장, 열화(포트 실패·스냅샷 없음·0건)에도 목록은 뜬다. 정렬 = 등록 최신순 고정(M8 전). 홈 미노출 유지. 프론트 `/bookmarks` 보드 렌더 | 1일 | ✅ 격리·열화·정렬 인터랙터 테스트 4종 + recommendation 20·stock 203 통과·계약 5 KEPT·tsc 0 |
| M8 | **개인화 ② — 선호 프로파일** (recommendation 확장) · **수요 게이트 뒤**. 북마크(명시 신호)와 대화 이력(암묵 신호 — `conversations.user_id` + `messages.payload`의 종목·상권 카드)에서 선호 업종·지역·섹터를 추출해 추천 정렬과 M7 보드 순서에 반영한다. **chat은 스포크라 recommendation이 직접 조인하지 않는다** — 허브에 이력 읽기 포트를 신설해 경유한다. **착수 조건**: 실사용자 확보. 사용자가 1명이면 개인화 효과(적중률·A/B)를 **측정할 자체가 없고**, 측정 없는 개인화는 이 저장소가 E2에서 거부한 바로 그것이다. 그때까지는 M7의 정렬 = 등록 최신순 고정 | 4-6일 | 착수 조건(실사용자 N명)이 곧 게이트. 통과 후에도 효과 지표를 먼저 정의하고 시작한다 |

---

## 새 도메인(스포크) 판정

| 후보 | 판정 | 근거 |
|------|------|------|
| 북마크/관심종목 | recommendation **확장** | "추천 기록"과 "찜"은 동일한 사용자↔분석대상 연결. CRUD 2-3개짜리 새 스포크는 과설계 |
| 개인화(관심 상태 보드·선호 프로파일) | recommendation **확장** (③-M7·M8) | 북마크와 같은 판정 논리 — "사용자↔분석대상 연결"의 심화다. 상태 표시는 허브 포트 재사용이고 선호 추출도 같은 애그리거트를 읽는다. 별도 스포크로 떼면 북마크와 사용자 축이 두 곳으로 갈라진다. 단 **chat 대화 이력은 허브 포트 경유**(스포크 간 직접 조인 금지) |
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
| E2 | ~~**펀더멘털 → 판정 편입**~~ — **완료·기각(2026-08-21)**. 백필: DART 소급 대신 **yfinance 연간 재무제표**(미국·한국 모두 4개 회계연도 제공 — 실측 확인, DART 경로는 한국 2종목뿐이라 불채택)로 `backfill_fundamentals.py` → `fundamental_snapshots(source='yf-hist')` 308행·78종목. **point-in-time: as_of = 회계연도말 + 90일**(공시 시차 — 연도말로 넣으면 미공시 실적을 아는 셈). 백테스트: `backtest_fundamentals.py` — PER/PBR 횡단 5분위 × 60/120거래일 워크포워드, 초과수익 = 유니버스 평균 차감. **결과: 전 조합 게이트 미달 — 역방향**(Q1 저평가 -2.2~-3.7%p, PER Q5 고평가 +1.7~+4.7%p, 2022-10~2026 성장주 주도장). 게이트에 **중첩 보정 유효표본**(월간 평가 × 60/120일 창 겹침 → n÷(h/21))을 썼다 — 원표본이면 소표본 낙관. **판정 편입 보류, 펀더멘털은 서술 축 유지.** 생존 편향·3년 창 한계 병기 → [[minseok/apps/stock/_docs/FUNDAMENTAL_BACKTEST_2026-08\|FUNDAMENTAL_BACKTEST]] |
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
  2. ~~국토부 실거래가 API~~ — **완료(2026-08-21, 매매 축으로 조정)**. `commercial_trades`
     (market 체인 `c7d8e9f0a1b2`) + `collect_commercial_trades.py`(매월 3일 cron, 백필
     2024-01~ 27,726건) + `asset_price` 서술(자치구 평당 중앙 매매가 + 서울 내 순위).
     **⚠ "임대 부담" 축은 미완** — 상업업무용 임대(전월세)가 국토부 공개 API에 존재하지
     않는다(2026-08-21 확인). 임대료는 한국부동산원 R-ONE 임대동향조사(별도 인증키 신청
     필요)가 후속 후보. YoY는 구성 잡음(실측 ±130%)이라 서술하지 않는다 → market CLAUDE 정본.
  3. **서울 지하철 승하차(일 단위)** — 후보 유지. 분기 유동인구의 고빈도 프록시.
  비공공(지도 리뷰·SNS 스크래핑)은 약관 리스크 대비 이득 부족으로 비추천.

## 명시적 비추천 (과설계 목록)

메시지 브로커·MSA 분리 / K8s·클라우드 /
MLflow·Airflow·DVC / 알림 스포크 선제 신설 / paid·결제 / SNS 로그인(껍데기 버튼 제거) /
admin 6페이지 전면 구현 / 커버리지 수치 목표 / GraphQL·BFF /
자동 배포 파이프라인(③까지 deploy.sh 수동 1커맨드) /
**R 트랙 한정**: 벡터DB 교체(Qdrant·Weaviate) · 청킹 라이브러리 도입 ·
LangChain retriever 체인으로 검색 경로 대체 · 실험 관리 도구 — 전부 pgvector + pytest + JSONL 안에서 끝낸다

**도입 예정으로 옮긴 항목** (2026-07-28) — 비추천 목록에서 뺐지만 무제한 승인은 아니다.
각 하네스의 게이트를 통과한 범위에서만 들어온다.

| 항목 | 상태 | 게이트 |
|---|---|---|
| 랭체인 | **도입됨** — `langchain-core` 1개, 허브 랭체인 게이트웨이(ROM 2.0) 1파일 | [[minseok/apps/admin/_docs/langchain-harness\|langchain-harness]] §5 (패키지 추가 시마다 재통과) |
| Neo4j 그래프DB | **도입 예정 · 시점 미정** — 아직 그래프 접속 코드 0건, `graph/` 선채우기 금지 유지 | [[minseok/apps/admin/_docs/neo4j-harness\|neo4j-harness]] §5-5 (그래프로만 답하는 질문·제약 Cypher·투영 경로·장애 격리) |
