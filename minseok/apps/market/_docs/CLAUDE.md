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
앱별 DB 불가침. 스키마 진실은 `apps/market/alembic` 독립 체인(7c5cfbd1c35f → 8d6efce2a41b → 9a1b2c3d4e5f → f3e4d5c6b7a8 → f4e5d6c7b8a9 → b5c6d7e8f9a0 → c7d8e9f0a1b2 → d8e9f0a1b2c3 → d8f0a1b2c3d4 → e9a1b2c3d4e5 → f5a6b7c8d9e0 → a6b7c8d9e0f1),
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
- `scripts/collect_seoul_quarter.py` — **신규 분기 자동 적재(③-M5, 2026-08-23)**. 주 1회
  폴링(공개 시점 불규칙): DB 팩트별 최신 분기 → 후보 분기를 OpenAPI로 수집 → API 코드를
  한글 CSV 헤더로 변환(`*_API_COLUMN_MAP` 6종 — CSV 맵과의 ORM 컬럼 동등성은
  `tests/adapter/test_column_maps.py`가 고정) → 연도별 CSV 병합(같은 분기 교체 멱등) →
  `ingest_seoul_3nf.py` 재사용. ⚠ 분기 필터는 서비스마다 갈린다(매출·점포·유동·상권변화만
  서버 필터, 상주·직장·집객은 무시 → 전량 후 분기 분해 — 2026-08-23 실측) · INFO-200은
  미공개 분기의 정상 응답. 소득소비·아파트는 API ERROR-500이라 제외(CSV 수동 유지).
- CSV→ORM 매핑은 `adapter/outbound/csv/column_maps.py`(스크립트 전용).
- 개별 `/admin/ingest/*` 라우터는 제거됨(스크립트로 대체).

## 조회

| 경로 | 구현 |
|------|------|
| chat(허브 포트) | `adapter/outbound/gateways/commercial_data_gateway.py` — `CommercialDataPort` 구현. 정규화 조인으로 원시 DTO 반환. → hub CLAUDE |
| 프론트 `/market/areas` | `area` 조회 슬라이스 — `trade_area` + region 조인으로 `Area` 엔티티 반환 |
| 프론트 `/market/areas/ranking` | `area_ranking` 조회 슬라이스 — **상권 디렉터리**(전 상권 최신 분기 매출·점포·점포당매출·QoQ·폐업률). 필터는 자치구·상권구분(`trade_area_division`)·업종. 상권당 쿼리가 아니라 GROUP BY 3개로 1,650행을 0.1초에 낸다(상권 1곳씩 `area_score`를 부르면 1만 쿼리). **정렬·검색은 하지 않는다** — 지표를 다 실어 보내고 프론트가 `useMemo`로 좁힌다(`admin/areas` 선례). 조건에 맞는 상권이 없어도 404가 아니라 빈 목록 |
| 프론트 `/market/trdar/{code}/stats` | `area_stats` 조회 슬라이스 — 상권 1곳의 분기 시계열(매출·점포·유동인구 병합) + 최신 분해축(연령/시간대) + 변화지표·시도 벤치마크. `service_code` 생략 시 최신 분기 매출 최대 업종 자동 선택 |
| 프론트 `/market/trdar/{code}/score` | `area_score` 조회 슬라이스 — 분기 추이(전 업종 합계 매출·유동인구 QoQ·YoY) + 서울 중앙 상권 대비 종합점수 **v2**(2026-09-17). 계산은 순수 도메인 서비스 `domain/services/area_scorer.py`(3축 — 4분기 폐업률 0.45·평균 영업 개월 0.33·점포당 매출 수준 0.22, 50=서울 중앙 상권, 가용 가중 평균). 입력 조립·중앙값은 `inputs_from_aggregates`·`median_inputs`(런타임·백테스트 공유) |
| 프론트 `/market/trdar/{code}/detail` | `area_detail` 조회 슬라이스 — 팩트별 최신 분기 구조 분해(요일·시간대·성별·연령대 매출, 상주·직장인구 피라미드, 가구·아파트, 소비 카테고리) + 규칙 기반 해석 문장. 문장 생성은 순수 도메인 서비스 `domain/services/area_narrator.py`(임계값 기반, LLM 미사용). 지도 오버레이 패널용 + 허브 `get_area_insights`로 chat에도 공급 |
| 프론트 `/market/trdar/{code}/fitness?service_code=` | `area_fitness` 조회 슬라이스(2026-09 game에서 이관) — 상권×업종 **입지 적합도 4축**(수요 정합·시간대 정합·경쟁 여유·생존 신호, 가중 합 0~1) + 실데이터 숫자로 말하는 진단 문장. 판정은 순수 도메인 `domain/services/area_fitness.py`, 문장은 `area_fitness_narrator.py`(템플릿, LLM 미사용). 입력 분포·서울 백분위는 `pg/area_demand_profile_pg_repository.py`(조회 6번, **최신 적재 분기**). 창업비용·임대료 같은 가정치는 없다(ROADMAP B4). 상권·업종 부재는 404 |
| **공개** `/market/areas/{code}/public` · `/market/areas/public-index` | `area_public` 슬라이스(A-4, 2026-09-14) — showcase에 이어 인증 없이 열리는 두 번째 경로. 상세·점수 유스케이스를 **조합만** 하고 `AreaPublicView`가 공개 필드를 명시(핵심 요약·점수·해석 문장 — 좌표·인허가 상호·인구 피라미드·업종 랭킹 표 없음). 인증 대신 `core/rate_limit`(60/분·10/분) + 하루 캐시. 인덱스는 차원 목록(코드·이름·자치구·유형)뿐. 공개 집합·rate limit 부착은 `minseok/tests/test_public_routes.py`가 고정 |
| (허브 적재) `POST /automation/franchise-costs` | 공정위 가맹정보 **업종별 창업비용** — 브랜드별 정보공개서(천원, 1만 1천여 건)를 업종 중분류별 **중앙값**·평균·브랜드 수로 우리가 집계(업종별 API는 단위·정의 불명확해 미사용) — `franchise_industry_costs`(year·sector·industry_name 교체 멱등, 리비전 d8f0a1b2c3d4). 수집 `scripts/collect_franchise_costs.py`(k3s CronJob 매월 1일 03:30, data.go.kr `DATA_GO_KR_API_KEY` + 해당 서비스 **활용신청 필요**). 읽기는 허브 `CommercialDataPort.get_startup_costs()`(chat 예산 답 — 예산의 70%까지를 창업비용으로 잡는 가정치, 임대료·인테리어 제외 고지) |
| 프론트 `/market/trdar/{code}/finance?service_code=&equity=…` | `area_finance` 조회 슬라이스(2026-09, FINANCE_ENGINE) — 사용자 입력(자기자본·보증금·월세·면적·인원·희망대출) + 상권 점포당 월매출·R-ONE 임대료·공정위 창업비용·ECOS 금리 → 순수 `domain/services/finance_engine.py`(BEP·부족 자금·runway·금리 +1/+2%p·3시나리오). 값마다 출처 태그, 첫 줄은 `finance_narrator`. 허브 `AreaFinancePort`로 chat에도 공급. 임대료 미적재 + 월세 미입력은 404 |

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

**미소비 컬럼 소진(2026-07-27, 7~10단계)** — 남아 있던 60컬럼 중 **43개**를 파생 신호로 소진했다.
나머지 17개(`resident`/`working`의 성별·연령 *합계*, `non_apartment_household_count`)는 이미 읽는
`male_age_*`/`female_age_*`의 덧셈이라 **의도적으로 만들지 않았다** — 새 정보가 0이다.

- `demand_purchasing_power`·`demand_unit_size` — 아파트 가격 7구간·면적 5구간.
  avg_price 하나로는 "고가 단지가 섞인 상권"과 "고르게 중저가인 상권"이 같아 보인다.
- `facility_character` — 시설 13종을 유입의 *종류* 4축(광역관문·학교·야간체류·생활편의)으로
  묶어 **처음 걸리는 하나만** 낸다. `facility_anchor`(유입의 *세기*)와 축이 다르다.
- `avg_ticket_time`·`avg_ticket_gender`·`traffic_vs_sales_gender` — 매출 건수 축과 통행 성별.

> **임계값은 전부 실측 분위수에서 잡는다.** 상식적인 값을 쓰면 서울 데이터에서 아무것도
> 안 뜨거나(시설: 학교·야간체류 중앙 0·p90 1 — "5곳 이상"이면 전 서울 2상권) 절반이 뜬다.
> 그리고 **집계 단위를 코드 경로와 맞춰야 한다** — 성별 괴리를 전 업종 합산으로 재면 중앙
> 8.2%p지만 실제 경로(대표 업종 1개)는 14.8%p여서, 합산 기준으로 잡은 0.15는 48%가 떴다.

**소득 데이터 공백(2026-07-27 발견)** — `consumption.monthly_avg_income`은 **2019년 4개
분기에만 있다**(서울시가 2020년부터 제공 중단). `find_spending`이 최신 분기를 읽으므로
`spending_power`의 소득 문장은 **2020년 이후 한 번도 뜬 적이 없었다**(지출 카테고리 분기로
조용히 열화). 100% 채워진 `income_range_code`(1~10)의 **서울 내 백분위**로 대체했다 —
구간 숫자 자체는 사용자에게 의미가 없어 상대 위치로만 노출하고, 구간 5·6에 1,137/1,622상권이
몰려 있어 **양 끝(상위/하위 25%)만 말한다**.

팩트별 개별 조회 슬라이스(라우터·인터랙터·리포지토리·매퍼·엔티티)는 제거됨 —
런타임 조회는 위 다섯 경로로 수렴한다. 팩트 ORM은 게이트웨이·적재 스크립트·마이그레이션이 사용하므로 유지.

## 인허가 업소 (업소 단위 개폐업)

분기 팩트 `store`는 점포 **수**라 "지난달 어떤 가게가 새로 열었나"를 못 답한다.
`business_permits`는 업소 한 곳이 한 행이고 인허가일·폐업일을 그대로 들고 있어 임의 기간을 센다.

- **출처는 localdata.go.kr이 아니다.** 그 호스트는 백엔드 PC에서 TCP 443이 닿지 않는다
  (2026-07-30 확인, DNS는 풀림). 같은 원본을 서울 열린데이터광장이
  `LOCALDATA_072404`(일반음식점 535,715) · `LOCALDATA_072405`(휴게음식점 146,579)로 주고,
  기존 상권 수집과 같은 창구·키(`SEOUL_OPENDATA_API_KEY`)를 재사용한다.
- **수집**: `scripts/collect_business_permits.py`(주 1회 화 05:00 cron, 683요청·약 10분).
  `(service_id, mgt_no)` 유니크로 멱등. **같은 청크 안의 중복 키를 먼저 제거해야 한다** —
  원본에 실제로 중복이 있어(6,000건에 1건) 그대로 넣으면 PostgreSQL이
  `ON CONFLICT DO UPDATE cannot affect row a second time`으로 죽는다.
- **상권 매칭**: 원본 X/Y가 `trade_area.x_coord/y_coord`와 같은 EPSG:5174라 변환 없이 거리로 붙인다.
  폴리곤이 없어 면적에서 원 근사(반경 = √(area/π), 중앙 151m). 격자 인덱스로 전수 비교를 피한다.
  **실측: 682,294건 중 331,920건(48.6%) 매칭, 1,489/1,650 상권에 업소가 붙는다.**
  반경 밖·좌표 없음은 `trdar_code` NULL(서울 전역 업소 중 상권 밖은 정상적으로 존재).
- **노출**: `area_detail` 슬라이스의 `permit_churn` + 서술 `permit_churn` + 프론트
  `PermitChurnSection`("요즘 뭐가 열고 닫나", 상호·업태·날짜).
  임계값은 업소가 붙은 1,489상권 실측 분위수 — **순증률 중앙이 -1.5%**라(서울 요식업 전반 감소)
  "순증=좋다"가 아니라 양 끝(p10 -10.3% / p90 +4.8%)만 말하고, 영업중 20곳 미만은 침묵한다.
- **영업중 수를 `store`의 점포 수와 나란히 두지 않는다** — 출처도 집계 기준도 다르다.
  사용자가 검산하려 들면 반드시 어긋난다.

## 상가 매매 실거래 (진입 비용 축)

분기 팩트는 매출·인구만 있고 부동산 가격이 없다 — 상권 축의 비용 공백을 국토부
실거래(`commercial_trades`, 리비전 `c7d8e9f0a1b2`)로 메운다.

- **임대는 없다.** 국토부 공개 API에 상업업무용 전월세가 존재하지 않는다(2026-08-21 확인 —
  `RTMSDataSvcNrgRent` 등 NO_OPENAPI_SERVICE). 매매만 적재하며, 임대료 축은 한국부동산원
  R-ONE 임대동향조사(별도 인증키)가 후속 후보다.
- **수집**: `scripts/collect_commercial_trades.py`(매월 3일 04:30 cron, `DATA_GO_KR_API_KEY`).
  원본에 거래 고유 ID가 없어 **(자치구, 거래 연월) 단위 DELETE 후 INSERT 교체**가 멱등
  규칙이다. 해제 신고(cdealType='O')는 거래 몇 달 뒤 붙기도 하므로 기본 실행이 최근 3개월을
  재수집한다(해제 거래는 적재 제외). 백필 2024-01~ 27,726건(집합 22,072).
- **상권 매칭 없음 — 자치구 단위다.** 원본에 좌표가 없다(법정동·지번뿐, 일반건물은 지번
  마스킹). 법정동 시군구코드(sggCd)가 region 자치구 코드와 동일 체계(11680=강남구 확인)라
  자치구로 집계한다. `umd_nm`(법정동명)은 향후 좁힐 때를 위해 원문 보존.
- **노출**: `area_detail`의 `find_asset_price` → 서술 `asset_price` 한 줄(구조 필드 없음 —
  문장이 전부다). **집합건물만** 집계한다(호실 = 창업자가 실제 사고 파는 단위, 일반 통건물은
  토지 비중이 커서 다른 모집단). 기준일은 오늘이 아니라 데이터 최신 거래일(신고 지연 방어,
  permit 선례). 25개 구 전부 최근 12개월 n=90~1,473이라 표본 걱정은 없다.
- **전년 대비(YoY)를 말하지 않는다** — 구 중앙 평단가의 YoY는 실측 ±130%까지 튀는
  **구성 잡음**(고가 신축 분양 믹스)이라 "올랐다/내렸다"가 허위가 된다. 절대 평단가(평당
  중앙)와 서울 내 순위만 사실 서술한다. 구 이름·"매매"를 문장에 명시한다(상권 시세·임대료로
  오독 방지).

## 창업비용 회수기간 (B8, 2026-09-14)

`franchise_industry_costs`(B7)를 상권 서술에 처음 결합한 팩트 — `area_detail`의 `payback` 한 줄(구조 필드 없음).
`창업비용 ÷ 선택 업종 점포당 월매출`로 **매출 N개월치**(가정 없는 사실)와 **외식업 평균 영업이익률 8.7% 가정 시 회수 약 k년**
(`cost_benchmarks.EATOUT_MARGIN`, 농촌경제연구원 외식업체 경영실태조사 2024)을 한 문장에 병기하고, 창업비용에 임대료·권리금이 없음을 명시한다.
- **2026-09-17 개정**: 전 업종 15%(9/14 확정값)는 출처가 없고 외식 실측의 1.7배라 회수기간을 짧게 보였다. 이익률 출처가 확인된
  외식 3군(음식점·카페·주점, `VERIFIED_MARGIN_GROUPS`)만 년수를 내고, 편의점·이미용·세탁은 매출 배수만 말한다(년수 미산출 명시).

- 서울시 업종명 → 공정위 중분류 매핑(`_FRANCHISE_INDUSTRY_BY_SERVICE`, 14종)은 narrator가 소유한다 —
  가맹 업종이 아니면(의약품 등) 조회 자체를 생략한다. 창업비용 조회는 `find_startup_cost(industry_name)`(최신 연도).
- 침묵: 창업비용 미적재 · 선택 업종이 랭킹 상위 12 밖 · 점포 5개 미만(9/8 소표본 규칙) · 점포당 월매출 0.
- ⚠ `find_service_ranking`의 `monthly_sales`·`sales_per_store`는 9/8 분기→월 환산(÷3)에서 **빠져 있었다**
  (다른 repo 4곳은 적용됨) — 이 팩트의 분모라 같이 고쳤다. 상세 응답의 업종 랭킹 금액도 이때부터 월 단위다.
- chat 노출은 `_INSIGHT_PRIORITY`(상위 4개)에 `payback`이 없어 아직 도달하지 않는다 — window 후속.

## 임대료·금리 (창업 재무 엔진, 2026-09)

- `rent_benchmarks` — R-ONE 상가 임대동향(소규모·중대형·집합) 서울 64 CLS × 분기(2024Q3~), 임대료 원/㎡·공실률.
  수집 `scripts/collect_rone_rent.py`(분기 첫 달 10일 cron). 상권 매칭은 `domain/services/rent_matcher.py`
  (R-ONE 상권 59개 별칭 → 자치구 권역 → 서울). **대부분 권역 평균**이라 서술이 "동북권 평균"임을 병기한다.
  **수익률 3열(2026-09-17, 리비전 a6b7c8d9e0f1)**: 같은 표 계열의 임대동향 수익률(소득·자본·투자, 분기 %)을 (분기, CLS_ID)로 붙인다 —
  512행 전부 키 일치 실측. chat 비교표에 "상가 수익률(분기, 소득·자본)" 행으로 노출(자본수익률 = 상권 자산가치 과열·침체 신호).
- `key_money_benchmarks`(2026-09-17) — R-ONE `A_2024_00445` 시도별/업종별 상가권리금(연간 2022~) 중 서울 × 업종 대분류 6개.
  같은 수집 스크립트가 적재. **재무 엔진의 권리금 기본값**: `domain/services/key_money.py` — 서울시 업종 코드 →
  대분류(외식 CS1·숙박 → 숙박 및 음식점업, 소매 CS3 → 도매 및 소매, 오락·미용 등 일부 CS2 → 해당 대분류, 나머지 → 전체).
  권리금 있는 점포 비율 50% 이상이면 **중위수를 가정**(2025 숙박·음식점업 80.4%·3,990만원), 미만이면 0으로 두되 비율·중위수를
  가정 문구에 병기(2025 도매·소매 31.3%). 이전 "권리금 0 가정"은 카페·음식점 부족 자금을 크게 과소평가했다. 사용자가 권리금을 말하면 입력이 이긴다.
- ECOS 추가 후보 검토(2026-09-17, 미채택): 지역별 소비유형별 신용카드(601Y002)는 2023-08에서 갱신 중단,
  은행 연체율(901Y054)은 기업·가계 구분뿐이라 자영업자 신호가 아니다.
- `interest_rates` — ECOS 기준금리·대출평균·기업대출 월별. 수집 `scripts/collect_ecos_rates.py`(매월 15일).
- 원가율·최저임금·기본 면적·보증금 개월·운전자금 개월은 `domain/services/cost_benchmarks.py` 상수(잠정, 출처 병기).
- **이익 과대 교정(2026-09-17)**: 고정비가 월세·인건비·이자뿐이고 인원 미입력 시 인건비 0이라 1인 카페 이익률이 최대 ~70%로 계산됐다
  (같은 파일의 카페 영업이익률 벤치마크 14%). ① 인원 미입력이면 점주 본인 최저임금 1인분(`DEFAULT_WORKERS`)
  ② 원가율에 카드 결제 수수료 1.5%(`CARD_FEE_RATIO`, 가정) 가산 ③ 계산 이익률이 업종 `margin_ratio`의 1.5배를 넘으면
  헤드라인이 경고하고 "업종 평균 이익률로 보면 월 이익 약 X"를 병기. 공과금·소모품·배달 수수료는 여전히 미반영이라 가정 문구에 명시.
  외식 3군 `margin_ratio`는 2026-09-17 잠정 12~14% → 실측 8.7%(`EATOUT_MARGIN`)로 교체 — B8 회수기간과 같은 값. 나머지 군은 잠정치.
- **잔여(2026-09-16)**: ① 골든셋 러너(`-m ollama`) 재박제·`finance_answer_rate` 실측은 백엔드 PC 전용이라 미실행
  ② R-ONE 상권 직접 매칭률 실측 미완 — 맥 로컬 DB에 `trade_area`가 없어 백엔드 PC DB 접속이 필요하다
  ③ dev 파드 실 DB curl 검증 미실행(파드 미기동).
- **배포 체크리스트**: ① `infra/k8s/load-image.sh`로 이미지 재빌드(cron 스크립트는 이미지 `/app`에 들어간다)
  ② `alembic -c apps/market/alembic.ini upgrade head` 수동 실행 ③ `/market/trdar/{code}/finance` curl 1회
  ④ `collect_rone_rent.py --dry-run`·`collect_ecos_rates.py --dry-run`.

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
- **하이브리드 검색(R2, 2026-08-23)**: `MarketNewsPgRepository.search_hybrid` — 벡터 +
  trigram 키워드(`pg_trgm similarity`, market 체인 `d8e9f0a1b2c3`) 채널을
  RRF(`domain/services/rrf_fusion.py`, k=60)로 결합하는 **실험 경로**(stock과 같은 규칙).
  유스케이스는 현행 순수 코사인 유지 — 게이트 통과 시에만 전환(ROADMAP R2).

## 점수 백테스트 (워크포워드 검증)

area_score의 예측력 실측 — 분기 t까지의 데이터만으로 점수·등급을 재현해 **그 뒤 1년(t+1~t+4)의
점포 가중 폐업률**과 대조한다(v2, 2026-09-17 — 이전 주 결과였던 t+1 상대 유동인구 QoQ는 참고치로 유지).

- **배치**: `scripts/backtest_area_score.py` — k8s CronJob `backtest-area-score`(매주 목 06:00). 동기 엔진으로
  팩트 벌크 로드 → 런타임과 같은 `inputs_from_aggregates`·`median_inputs`(그 분기의 서울 중앙값) →
  순수 `AreaScorer` → `area_score_backtest_reports`에 실행당 1행(payload JSONB, `outcome: closure_next4`) INSERT.
- **집계**: `domain/services/area_score_backtester.py`(순수) — 등급별 향후 폐업률·컴포넌트별
  Spearman(폐업률 부호 반전 — 양수면 점수가 높을수록 덜 닫음)·5분위 스프레드(하위−상위 폐업률). payload 스키마의 단일 정의처.
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
- **2026-09-17 점수 v2 재설계**: 결과를 "향후 1년 폐업률"로 재정의하고 후보 지표를 실험(관측 23,009 ·
  학습 2022~23 / 검증 2024~25 분할, 분기 내 Spearman 평균). 과거 4분기 폐업률 IC 0.34 · 평균 영업 개월 0.33 ·
  점포당 매출 수준 0.11 · v1의 매출/유동인구 QoQ 0.00~0.02 · 개폐업 순증 -0.02 · 점포 수 YoY -0.05(제외).
  검증 기간 종합 IC **v1 0.19 → v2 0.37**. 벤치마크를 서울 합계 평균에서 **중앙 상권(중앙값)**으로 바꿔
  등급 경계(80/65/45/30)를 유지한 채 분포가 가운데로 모였다(실 DB: 우수 2%·양호 12%·보통 50%·주의 29%·위험 7%).
  v2 백테스트(관측 24,750): 등급별 향후 1년 폐업률 우수 2.01% → 양호 2.42% → 보통 2.95% → 주의 3.34% → 위험 3.74%(단조),
  컴포넌트 ρ closure_stability +0.333 · persistence +0.317 · sales_level +0.105.
- **2026-09-17 점포 수 모수 교정**: 원본 `점포_수`(`store_count`)는 **프랜차이즈를 뺀 값**이다 — `점포_수 + 프랜차이즈 = 유사업종`이
  168만 행 전부 성립하고, 추정매출·폐업 점포·서울시 공식 폐업률(치킨 1÷31=3%)은 전체(유사업종) 기준이다. `store_count`로 나눠
  편의점 점포당 매출이 3.2배(1.6억), 치킨 2.5배로 부풀었고 폐업률도 프랜차이즈 비중만큼 과대, 프랜차이즈만 있는 4.7만 행은
  `store_count > 0` 필터에 걸려 매출이 통째로 빠졌다. **점포 수·점포당 매출·판정 폐업률의 분모는 전부 `similar_industry_store_count`**
  (점수·랭킹·상세·적합도·chat 게이트웨이·백테스트 스크립트). 원본 `store_count`는 `/stats` 분기 시계열의 원값 표시에만 남는다.
  교정 후 백테스트(관측 24,750): 우수 1.93% → 양호 2.25% → 보통 2.70% → 주의 3.05% → 위험 3.43%(단조 유지),
  ρ closure_stability +0.296 · persistence +0.293 · sales_level +0.150. 가중치(.45/.33/.22)는 교정 전 데이터로 정한 값 그대로다.

## 조회 성능 — 인덱스·캐시 (2026-07-27)

2021~2024 백필로 팩트가 20분기가 되면서 두 가지가 드러났다.

- **복합 인덱스**: 팩트 조회의 지배적 패턴은 `WHERE trdar_code=? ORDER BY year_quarter DESC`
  인데, 기존엔 단일 인덱스뿐이라 `uq_*`(선두 `year_quarter`) 역방향 스캔으로 샜다.
  9팩트에 `ix_<fact>_trdar_quarter`를 만들고(리비전 `a1b2c3d4e5f6`), 접두사로 잉여가 된
  `ix_<fact>_trdar_code` 9개를 제거했다(`b2c3d4e5f6a7`). `ix_<fact>_year_quarter`는 유지 —
  `area_ranking`의 `WHERE year_quarter=?`와 벤치마크 캐시의 `max(year_quarter)`가 쓴다.
  실측: `store` 최신 1건이 670버퍼·2.2ms → **4버퍼·0.065ms**.
- **시도 벤치마크 캐시**(v2에서 대상이 `find_city_score_medians` — 서울 1,650곳 중앙값 — 로 바뀜, 첫 계산 1.9초·이후 상권당 7ms):
  원래 `find_city_*_series`는 **상권과 무관하게 같은 값**인데 `/score`
  요청마다 재집계했다(1회 55,977버퍼로 5행). 최신 분기를 버전 키로 한 모듈 캐시를 붙였다 —
  분기 적재가 들어오면 자연 갱신(stock_forecast의 마지막 봉 ts 선례와 같은 방식).
  **캐시 키에 `quarters`를 넣지 않는다** — 화면이 4/8/20분기를 오갈 때 캐시가 조각난다.
  항상 `MAX_QUARTERS`(=20, `area_scorer` 소유) 창을 캐시하고 요청분만 잘라 쓴다.
  실측: `/score` 첫 호출 330ms → 캐시 히트 **12.4ms**.

> Redis·사전집계 테이블은 쓰지 않는다 — 단일 프로세스이고 캐시 대상이 시도 1 × 분기 20 ×
> 지표 3 = 60행이라 과설계다.

## 좌표

`utils/coords.py`의 `tm_to_wgs84`(EPSG:5174→4326)가 TM 좌표를 위경도로 변환한다.
`trade_area`·`Coordinate` VO가 `lat`/`lng` property로 노출한다.

---

## 남은 조회 슬라이스 컨벤션 (area)

로직(VO·계산)이 있는 기능에만 entity/vo/mapper를 둔다. `area`는 `Coordinate` VO가 좌표 변환을
소유하므로 `area_entity` + `area_mapper`를 둔다. 파일명은 도메인어(`area`, `trade_area` …)를 쓴다.
전체 수직 슬라이스 네이밍 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].
