# CLAUDE.md — market 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

서울 상권 분석 도메인 스포크. 상권 데이터(3NF)를 소유하고, 허브 포트 구현으로 chat에 제공한다.

---

## 문서

| 문서 | 내용 |
|------|------|
| [[minseok/apps/market/_docs/MARKET_ERD|MARKET_ERD]] | 3NF 스키마 — 차원 5 + 팩트 9, FK, 정규화 이력 |

---

## 전용 DB (2026-07-22 런타임 전환 완료)

market의 모든 테이블(3NF 15 + market_news_articles + area_score_backtest_reports)은
**전용 DB(market-pgvector, pg17+pgvector, 호스트 :5434)**에 산다. 접근은 market 프로바이더가
`core.database.get_market_db`(엔진은 `MARKET_DATABASE_URL`, 미설정 시 메인 폴백)로만 한다 —
앱별 DB 불가침. 스키마 진실은 `apps/market/alembic` 독립 체인(7c5cfbd1c35f → 8d6efce2a41b → 9a1b2c3d4e5f),
루트 체인의 market 리비전들은 이력 동결(루트 env.py에서 ORM 제거 + include_name 필터).
컨테이너 접속: 실운영 backend는 `host.docker.internal:5434`(네트워크 분리, extra_hosts).
백업: `scripts/backup_db.sh`의 market 블록(market-*.dump 7세대). 배치(ingest·backtest)도
`MARKET_DATABASE_URL` 우선. 메인 DB(5432)에 남은 market 테이블 사본은 롤백 안전용 —
삭제 시 루트 env.py 필터도 함께 제거할 것.

## 데이터 스키마 — 3NF

발자국 ERD 컨벤션을 적용한 정규화 스키마. 상세 → [[minseok/apps/market/_docs/MARKET_ERD|MARKET_ERD]].

- **차원(5)**: `region`(자치구→행정동 자기참조), `trade_area_division`, `service_category`,
  `change_indicator`, `trade_area`(중심).
- **팩트(9)**: `estimated_sales`·`store`(+service FK)·`floating/resident/working_population`·
  `consumption`·`apartment`·`facility`·`commercial_change`. 공통 `MarketStatMixin` = `id + year_quarter +
  trdar_code(FK→trade_area)`. 차원 속성(상권명·구분·지역명)은 차원 테이블로 정규화됨.
- 분해 컬럼(연령/시간/요일)은 넓게 유지 — 3NF 준수, 과정규화 회피.

## 적재 — 독립 스크립트

- `scripts/fetch_seoul_facility.py` — **집객시설-상권만 포털에 파일이 없어** OpenAPI
  (`VwsmTrdarFcltyQq`, `SEOUL_OPENDATA_API_KEY` 필요)로 받아 다른 CSV와 같은 자리·인코딩으로
  떨군다. 헤더는 API 필드 코드 그대로(포털이 한글 라벨을 공개하지 않아 지어내지 않았다).
- `scripts/ingest_seoul_3nf.py` — CSV(`data/raw/seoul/`, cp949)를 차원 먼저 → 팩트(FK 무결성 필터)로 적재.
  **모든 INSERT가 멱등**(`ON CONFLICT DO NOTHING`)이라 재실행이 안전하다. 서울시가 추정매출·
  점포를 연도별 파일로 주므로 `서울시 상권분석서비스(<팩트>)_<연도>년.csv`도 함께 읽는다.
  `--facts`(테이블 선택) · `--years 2021-2024`(연도 필터) · `--dry-run`(적재 없이 분기·FK
  탈락 건수만 보고) 지원. **백필 전 `--dry-run`으로 상권코드 매칭률을 먼저 확인할 것** —
  2021년 공간 단위 변경 이력이 있어 코드 체계가 다른 데이터를 섞으면 시계열이 조용히 오염된다.
  **분기 범위(2026-07-27 기준)**: 매출·점포 20211~20254(20분기, 2021~2024 백필 완료),
  나머지 6팩트 20191~20254. 2021년 이전 매출·점포는 서울시가 제공을 중단해 확보 불가.
- CSV→ORM 매핑은 `adapter/outbound/csv/column_maps.py`(스크립트 전용).
- 개별 `/admin/ingest/*` 라우터는 제거됨(스크립트로 대체).

## 조회

| 경로 | 구현 |
|------|------|
| chat(허브 포트) | `adapter/outbound/gateways/commercial_data_gateway.py` — `CommercialDataPort` 구현. 정규화 조인으로 원시 DTO 반환. → hub CLAUDE |
| 프론트 `/market/areas` | `area` 조회 슬라이스 — `trade_area` + region 조인으로 `Area` 엔티티 반환 |
| 프론트 `/market/areas/ranking` | `area_ranking` 조회 슬라이스 — **상권 디렉터리**(전 상권 최신 분기 매출·점포·점포당매출·QoQ·폐업률). 필터는 자치구·상권구분(`trade_area_division`)·업종. 상권당 쿼리가 아니라 GROUP BY 3개로 1,650행을 0.1초에 낸다(상권 1곳씩 `area_score`를 부르면 1만 쿼리). **정렬·검색은 하지 않는다** — 지표를 다 실어 보내고 프론트가 `useMemo`로 좁힌다(`admin/areas` 선례). 조건에 맞는 상권이 없어도 404가 아니라 빈 목록 |
| 프론트 `/market/trdar/{code}/stats` | `area_stats` 조회 슬라이스 — 상권 1곳의 분기 시계열(매출·점포·유동인구 병합) + 최신 분해축(연령/시간대) + 변화지표·시도 벤치마크. `service_code` 생략 시 최신 분기 매출 최대 업종 자동 선택 |
| 프론트 `/market/trdar/{code}/score` | `area_score` 조회 슬라이스 — 분기 추이(전 업종 합계 매출·유동인구 QoQ) + 시도 벤치마크 대비 종합점수. 계산은 순수 도메인 서비스 `domain/services/area_scorer.py`(4개 컴포넌트 0~100, 50=벤치마크 동률, 가용 평균) |
| 프론트 `/market/trdar/{code}/detail` | `area_detail` 조회 슬라이스 — 팩트별 최신 분기 구조 분해(요일·시간대·성별·연령대 매출, 상주·직장인구 피라미드, 가구·아파트, 소비 카테고리) + 규칙 기반 해석 문장. 문장 생성은 순수 도메인 서비스 `domain/services/area_narrator.py`(임계값 기반, LLM 미사용). 지도 오버레이 패널용 + 허브 `get_area_insights`로 chat에도 공급 |

**객단가 분해·통행 대조(2026-07-27)** — `estimated_sales`의 건수 축과 `floating_population`의
요일 축을 처음 쓴다. 금액만으론 "많이 오는 층"과 "비싸게 쓰는 층"이 구분되지 않는다.
- `avg_ticket_rhythm` 주중/주말 객단가 차이(20% 이상일 때만) · `avg_ticket_age` 최고 객단가
  연령대(건수 비중 5% 미만 층은 허위 최고가라 제외)
- `traffic_vs_sales` 통행 주말비중 − 매출 주말비중이 15%p 이상 벌어질 때 — "지나가긴 해도
  지갑은 평일에 열린다". 요일 7컬럼은 `FloatingRhythm`으로 주중/주말 2개로 접어 쓴다
  (7개를 그대로 노출하면 화면·스키마만 늘고 값하는 건 이 교차 신호 하나다).
- `facility_anchor` 지하철역·대학·백화점·버스정거장(30개+) — "여기 사람이 왜 오는가".
  시설 20종 중 외부 유입 동선을 만드는 것만 센다. 하나도 없으면 침묵한다(동네 상권을
  "유입이 강하다"고 말하면 거짓이다).

팩트별 개별 조회 슬라이스(라우터·인터랙터·리포지토리·매퍼·엔티티)는 제거됨 —
런타임 조회는 위 다섯 경로로 수렴한다. 팩트 ORM은 게이트웨이·적재 스크립트·마이그레이션이 사용하므로 유지.

## 상권 뉴스 (RAG 코퍼스)

market이 소유하는 두 번째 데이터 축 — 분기 공공데이터의 시의성 공백을 일 단위 기사로 보완한다.

- **테이블**: `market_news_articles` — (url, area_tag) 유니크, 제목 bge-m3 임베딩(1024, nullable).
  `area_tag`는 지역 어간(예: 성수) — 주식 뉴스의 ticker에 대응하는 결합 키.
- **수집**: `scripts/collect_market_news.py`(매일 01:30 cron) — Google News RSS
  "지역 어간 × 상권" + 정책 공통 키워드(`scripts/market_news_watchlist.txt`) → 허브
  `POST /automation/market-news`.
- **슬라이스**: `market_news_interactor`(적재+배치 임베딩+의미 검색) ← 허브 게이트웨이 2종
  (`market_news_storage_gateway` · `market_news_search_gateway`)이 위임. 소비는 chat(허브
  `MarketNewsSearchPort` 경유, 상권 답변 기사 근거). → hub CLAUDE

## 점수 백테스트 (워크포워드 검증)

area_score의 예측력 실측 — 분기 t 데이터만으로 점수·등급을 재현해 t+1 실제 결과
(상대 유동인구 QoQ = 상권 − 서울 %p, 계절성 통제)와 대조한다.

- **배치**: `scripts/backtest_area_score.py`(수동 실행, 분기 데이터 갱신 후) — 동기 엔진으로
  팩트 벌크 로드 → 순수 `AreaScorer` 재사용(분기 t의 정확한 QoQ만, 폴백 없음 — 룩어헤드 방지)
  → `area_score_backtest_reports`에 실행당 1행(payload JSONB) INSERT.
- **집계**: `domain/services/area_score_backtester.py`(순수) — 등급별 t+1 결과·컴포넌트별
  Spearman·5분위 스프레드. payload 스키마의 단일 정의처.
- **조회**: 허브 `AreaBacktestReportPort`를 `area_backtest_report_gateway`가 구현(최신 1건),
  admin `/admin/market-backtest`가 소비.
- **2026-07-27 재채점(매출·점포 2021~2024 백필 후)**: 매출·개폐업 축이 처음으로 실표본을
  갖췄다(`sales_growth` n=28,193 · `store_health` n=31,329 — 이전엔 2025년 4분기뿐이라
  저표본 참고치였다). 관측 42,879 · 상권 1,650 · 평가분기 26개(20192~20253).
  결과: 우수 등급 avg **+5.07%p**(n=527, 양(+)비율 56.0%)로 이전 +2.55%p보다 뚜렷해졌으나,
  컴포넌트 예측력은 여전히 약하다 — `sales_growth` ρ=-0.077(스프레드 -1.21%p, 평균회귀),
  `floating_growth` ρ=-0.030, `store_health` ρ=+0.010, `persistence` ρ=-0.012.
  **점수 v1은 여전히 "현황 요약"이지 t+1 예측기가 아니다.** 등급 경계 재설계와 결과 지표
  재정의(상대 유동인구 QoQ 대신 폐업률 등)가 후속 과제.

## 좌표

`utils/coords.py`의 `tm_to_wgs84`(EPSG:5174→4326)가 TM 좌표를 위경도로 변환한다.
`trade_area`·`Coordinate` VO가 `lat`/`lng` property로 노출한다.

---

## 남은 조회 슬라이스 컨벤션 (area)

로직(VO·계산)이 있는 기능에만 entity/vo/mapper를 둔다. `area`는 `Coordinate` VO가 좌표 변환을
소유하므로 `area_entity` + `area_mapper`를 둔다. 파일명은 도메인어(`area`, `trade_area` …)를 쓴다.
전체 수직 슬라이스 네이밍 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].
