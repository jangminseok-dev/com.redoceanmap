# CLAUDE.md — stock 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

주식 분석 스포크. 트레이더용 지표 + 뉴스 감성을 결합해 사용자가 물은 종목의
상승/하락 방향·확신도(장기 목표: 확률·매수 타이밍·지지/저항선 제시)를 알려준다.
매매 실행(주문/포지션)은 다루지 않는다 — 분석·정보 제공까지가 범위.

---

## 역할

- **대상 시장: 한국(코스피/코스닥) + 미국.** 한국 6자리 코드는 어댑터가 `.KS` → `.KQ` 순으로 해석.
- `StockInteractor`(대장)가 시세/지표 조회 → 뉴스 감성 점수화 → `OutlookPredictor`(도메인 서비스)로
  방향 전망 산출을 조립한다. 지표 계산(RSI·MA·지지/저항)은 `IndicatorCalculator`(순수 도메인)가 담당.
- 시세/지표/뉴스는 `YFinanceMarketDataAdapter`(yfinance, 키 불요·지연 시세). 실시간이 필요해지면
  KIS 등 벤더 어댑터로 교체한다(`MarketDataPort` 계약 동일). 헤드라인이 없으면 감성은 중립(0.0)으로
  두고 LLM을 부르지 않는다.
- 감성 점수화는 `ExaoneSentimentAdapter`가 LLM 오케스트레이터(기본 모델 7.8B — 단일 모델 정책)로 수행.
- **수집 뉴스(DB)**: n8n이 허브 `/automation/news`로 적재(허브 `NewsStoragePort`를
  `NewsStorageGateway`가 구현, `news_articles` 테이블·url 유니크). 분석 시 DB 뉴스를
  벤더(yfinance) 뉴스보다 우선 병합 — 한국 종목 뉴스 공백 해소. n8n은 허브만 안다.
- **워치리스트 3계층** (`scripts/news_watchlist.txt`, 뉴스·시세·펀더멘털 수집기 공유):
  ① 코어 68(한국 2 고정 — 추가 금지 2026-07-21 확정 + 빅테크·테크 28 + 업종 다양성 38,
  GME 포함, 수동 관리), ② `auto:screened` 10 — `scripts/screen_us_undervalued.py`(주 1회 cron)가
  yfinance 무료 스크리너로 미국 저평가 대형주를 PER+PBR 랭킹해 자동 교체(히스테리시스:
  기존 편입은 상위 20위 이내면 유지, 한국 기업 ADR 제외), ③ `auto:demand` ≤5 — 분석 질문
  수요(`stock_demand` 테이블, `StockInteractor`가 기록) 상위를 같은 스크립트가 편입,
  14일 질문 없으면 퇴출. 허브 `StockDemandPort`(`GET /automation/stock-demand`)가 조회 창구.
  기관등급(yfinance)은 429 방지를 위해 `collect_news.py --analyst`로 분리(일 1회 cron).
- **미수집 종목 라이브 폴백**: `stock_history`(1d)·`stock_forecast`는 DB에 봉이 없으면
  `MarketDataPort.daily_bars`(yfinance 2y)로 즉석 계산하고 응답에 `live: true`를 표기 —
  임의 티커도 첫 질문부터 차트·확률이 뜬다(저장 안 함, 5m는 폴백 없음). quote는 서버 측
  심볼당 20초 공유 캐시로 다중 사용자 폴링에도 벤더 호출을 상한한다.
- **뉴스 의미 검색(RAG)**: 적재 시 제목을 bge-m3(1024차원, 오케스트레이터 `embed_many` 경유)로
  임베딩(`news_articles.embedding`, 실패 시 NULL — 수집 우선·다음 주기 자연 재시도).
  허브 `NewsSearchPort`를 `NewsSearchGateway`가 구현 — pgvector 코사인 + 티커 하이브리드 필터 +
  news_labels 라벨 조인 + 제목 dedupe. 소비자는 chat(종목 질문 보강 + 시장 횡단 질문).
  백필은 `POST /automation/news-embeddings/backfill`. 벡터 인덱스는 10만 건+에서 hnsw 재검토.
  **하이브리드 검색(R2, 2026-08-23)**: `NewsPgRepository.search_hybrid` — 벡터 + trigram
  키워드(`pg_trgm similarity`, 루트 체인 `j9c0d1e2f3a4`) 채널을 RRF(`domain/services/rrf_fusion.py`,
  k=60)로 결합하는 **실험 경로**. 유스케이스는 현행 순수 코사인 유지 — R1 baseline 대비
  nDCG@5 +0.03 게이트 통과 시에만 전환(미달이면 기각, ROADMAP R2).
- **공시 청킹 실험(R3, 2026-08-23)**: DART 사업보고서(한국 10사 × 최신 1건)를 3전략으로
  청킹해 `disclosure_chunks`(루트 체인 `k0d1e2f3a4b5`, strategy 컬럼으로 병렬 저장)에
  적재하고 검색 품질을 비교한다 — 수집·임베딩은 `scripts/collect_disclosures.py`(교체 멱등),
  파서는 `adapter/outbound/dart/disclosure_parser.py`(비정형 `&`·`<` 전처리, 각주는 표 안
  `※` 행·다음 한 줄 안내 표·직후 P 3경로 승계 — `(주)상호`는 각주 아님), 청킹 규칙은
  순수 도메인 `disclosure_chunker.py`(a 고정 512자 대조군 / b 섹션 / c 표 행+헤더=값
  페어링+각주 인라인). 프로덕션 미편입 — 게이트((c)가 (a) 대비 표 질의 recall@5 +0.10)
  판정까지 실험 전용(ROADMAP R3).
- **수집 OHLCV(DB)**: cron(`scripts/collect_prices.py`, 뉴스와 워치리스트 공유)이 허브
  `/automation/prices`로 적재(허브 `PriceBarStoragePort`를 `PriceBarStorageGateway`가 구현,
  `price_bars` 테이블·(ticker, timeframe, ts) 유니크). 5분봉(60일 소급)·일봉(전체) —
  뉴스 발행 후 주가 반응 라벨링용. 장외 발행 뉴스는 "다음 개장 첫 봉" 기준으로 라벨한다.
- **수집 펀더멘털(DB)**: 주간 cron(`scripts/collect_fundamentals.py`, yfinance + DART 무료 API)이
  허브 `/automation/fundamentals`로 적재(허브 `FundamentalStoragePort`를 `FundamentalStorageGateway`가
  구현, `fundamental_snapshots` 테이블·(ticker, as_of, source) 유니크). PER/PBR/ROE/부채비율/FCF/EPS/BPS —
  버핏식 가치·체력 축. 한국 종목은 DART 연간 재무제표로 EPS/BPS→PER/PBR 자체 계산(source=dart 별도 행).
  판정(OutlookPredictor) 편입은 **백테스트로 기각됨(2026-08-21, E2)** — `backfill_fundamentals.py`
  (yfinance 연간 재무 4개년 → `source='yf-hist'` 백필, as_of = 회계연도말 + 90일 공시 시차) +
  `backtest_fundamentals.py`(PER/PBR 횡단 분위 × 60/120거래일 워크포워드)에서 전 조합
  게이트 미달·역방향. **펀더멘털은 서술 축으로만 유지**, yf-hist 행은 화면·채팅 조회에서
  제외된다(`find_latest_fundamentals`) →
  [[minseok/apps/stock/_docs/FUNDAMENTAL_BACKTEST_2026-08|FUNDAMENTAL_BACKTEST]].
- **뉴스 LLM 라벨(DB)**: 야간 cron(`scripts/label_news.py`, EXAONE 7.8B Ollama 경유 —
  도메인 내부 추론 계층 준수)이 허브 `/automation/news-labels`로 적재(허브 `NewsLabelStoragePort`를
  `NewsLabelStorageGateway`가 구현, `news_labels` 테이블·(news_id, labeler) 유니크).
  감성(-1~1)·이벤트 유형·확신도. 라벨은 피처, 정답은 실현 수익률 — 라벨 품질은
  price_bars 조인으로 사후 채점한다.
- **적재 현황 노출**: 허브 `StockDatasetStatsPort`를 `StockDatasetStatsGateway`가 구현 —
  뉴스·라벨·펀더멘털·예측 스냅샷·주가 봉 5테이블의 행수와 **최신 적재 시각(`created_at`)**을
  집계해 admin 데이터소스 화면(수집 신선도 배지)에 제공한다. 도메인 시각(`ts`·`as_of`·
  `published_at`)이 아니라 적재 시각인 것이 핵심 — 수집이 멈춘 것을 감지하는 용도다.
- **뉴스 이벤트 연구(2026-07-27)**: `domain/services/event_study.py`(순수) +
  `scripts/study_news_events.py`(수동 배치) → `news_event_study_reports`(실행당 1행 payload).
  허브 `NewsEventStudyPort`를 `NewsEventStudyGateway`가 구현, admin `/admin/news-event-study`가
  소비. hub 문서가 선언만 하고 비어 있던 `news_labels × price_bars` 조인이다.
  **기준선 대비로 읽는다** — 절대 수익률은 표본 기간 시장 방향을 반영해 전 유형이 음수로
  나온다. 표본 집중도 경고를 함께 내고 **사용자 화면에는 올리지 않는다**(뉴스 3개월 축적 후 재평가).
- **분 단위 지평 E1(2026-08-20)**: 같은 스크립트가 5분봉으로 발행 직후 30·60분 반응도 함께 낸다
  (`aggregate_intraday` → payload `short_horizon[]`, 허브 `ShortHorizonRow`, admin 화면 확장).
  기준(q0)은 발행 직후 첫 5분봉, 결과(q1)는 **그 봉으로부터** N분 뒤 첫 봉이다.
  ⚠ **q1을 `published_at + N분`에 걸면 안 된다** — 장 마감 뒤 발행이면 q0·q1이 같은 개장 봉으로
  떨어져 수익률이 0이 된다(2026-08-20 실측 표본의 75.1%, 양(+) 비율이 9%까지 내려간 가짜 리포트).
  장 마감을 걸쳐 경과가 지평의 3배를 넘는 표본은 제외한다(밤샘 갭은 분 단위 반응이 아니다).
  첫 실측: 30·60분 초과수익은 전 유형 ±0.13%p 이내로 **사실상 없음**. 반면 5일 지평에서는
  "강한 부정"이 +2.32%p로 최상위다 — 즉각 반응이 아니라 되돌림 구간에서 값이 나온다는 뜻.
  5분봉은 소급 수집이 안 되므로 표본 수를 일간과 직접 비교하지 않는다(`coverage_note`).
- **백테스트**: `Backtester`(순수 도메인) + `scripts/backtest_stock.py`. 워크포워드로 t까지의
  데이터만 써서 t+horizon 종가와 비교, 항상-UP 기준선과 대조한다. 과거 뉴스는 수집 불가라
  감성 중립(0.0) 고정 — 지표 신호만 채점.
  - **적중 정의(2026-08-28 변경)**: 부호(`ret > 0`)가 아니라 **변동성 초과** —
    `ret > ATR% × √horizon × HIT_Z_MIN(0.25)`. 정의처는 `backtest_report.py`의
    `hit_unit`/`is_up_hit`이고 **`Backtester`·`weight_refit`·스냅샷 채점이 반드시 같이 쓴다**
    (갈라지면 재적합이 백테스트와 다른 기준으로 승격을 결정한다). 기준선도 같은 규칙으로 세고,
    다종목 병합 기준선은 평가일이 아니라 **신호 수** 가중이다(`_weighted_baseline`).
    z=0.25는 20종목 5년 스윕에서 우위(하한−기준선)가 최대인 구간(0.25~0.35)으로 정했다.
    **옛 정의에서는 우위가 +0.01%p로 사실상 0** — 부호 채점은 "항상 매수"와 신호를 구분하지
    못했다. 단 새 정의로도 `ready`는 늘지 않는다(3/20 → 2/20). 상세 →
    [[minseok/_docs/SIGNAL_OVERHAUL_2026-08|SIGNAL_OVERHAUL]]
  - **스윕 결론 1차(2026-07 초, RSI+MA만)**: 어떤 가중치·임계값 조합도 기준선을 못 이김
    → 기본값(±0.3) 유지, 확률 제시 근거 부족.
  - **재채점 2차(2026-07-13, 피처 확장 — 로드맵 ①-M2)**: ATR·볼린저 %B·거래량비·OBV 추가,
    21조합 × 24종목 · 5y 스윕 + 판정 기준 명문화(n≥100 + Wilson 95% 하한 > 기준선,
    `backtest_report.py`). **RSI+BB ±0.35 UP 신호만 인샘플·홀드아웃(이전 5y) 양쪽 통과**
    (기준선 +1.9~2.1%p, 하한 마진 +0.4%p) — 첫 재현 양성 신호. 단 다중 비교 1건에 마진이
    얇아 **확률 제시는 계속 보류**, "참고 신호" 수준. OBV·ATR거부는 효과 없음. 다음 재채점은
    뉴스 감성 축적(~3개월) 후. 상세 →
    [[minseok/apps/stock/_docs/BACKTEST_RESCORE_2026-07|BACKTEST_RESCORE_2026-07]]
  - **재채점 3차(2026-07-14, 12-1 모멘텀 + 거래량 확인)**: `closes[-22]/closes[-253]-1` 모멘텀과
    `volume_confirm` 강등 필터 추가, 30조합 스윕(홀드아웃은 `--drop-last 1260`으로 재현).
    **RSI+BB+MOM(0.4/0.4/0.2) ±0.35 UP이 새 최우수 검증 신호**(인샘플 하한 +3.5%p·홀드아웃 +0.9%p,
    0.25 임계값도 연속 통과). 모멘텀 단독·거래량 필터는 기각, 하락 예측 불가 재확인.
    확률 제시·기본값은 계속 보류/불변. `analyze` 응답의 `reference_up_signal`은 2차 검증
    조합(RSI+BB ±0.35, `AnalysisConfig.rsi_bb_reference()`)을 노출 — 감성 재채점에서 재현 시 승격 재검토.
- **분석 API 노출 지표**: RSI(14)·MA20/50·지지/저항(60일)·ATR%·볼린저 %B·거래량비(5/20일)·
  OBV 기울기·12-1 모멘텀 + `reference_up_signal`(검증 참고 신호, 확률 아님). 시세 이력은 2y
  (모멘텀에 253거래일 필요).
- **수집 데이터 조회(프론트 자료 패널)**: `stock_history` 조회 전용 슬라이스 —
  `GET /stock/{symbol}/prices?timeframe=1d|5m&limit=`(OHLCV, ts 오름차순, 미보유 심볼 404),
  `GET /stock/{symbol}/news?limit=`(뉴스+라벨 조인, 발행일 내림차순),
  `GET /stock/{symbol}/fundamentals`(소스별 최신 스냅샷 + `fundamental_narrator` 규칙 해석 —
  PER/PBR/ROE, dart 우선 병합, debt_to_equity는 단위 혼재로 해석 제외). 분석(yfinance 라이브)과
  달리 DB 축적분만 읽는다. 거래소 접미 매칭(005930 ↔ 005930.KS)은 PG 리포지토리가 맡고,
  실제 저장 티커는 `resolvedTicker`로 노출한다.
- **판정 조합(2026-07-30, 2026-08-21 DB화)**: forecast·스냅샷 슬라이스는 **활성 판정 조합**
  (`forecast_signal_configs` 테이블, `SignalConfigPort.active()` — 행 부재 시
  `AnalysisConfig.forecast_signal()` 폴백, 시드 = RSI+BB+MOM 0.4/0.4/0.2 ±0.35)을 쓴다.
  활성 조합의 키가 forecast 캐시 키와 스냅샷 `signal_config` 스탬프에 들어가므로
  재적합 승격이 다음 요청부터 즉시 반영되고 이력이 조합별로 갈린다.
  `analyze` 경로의 `default()`는 **불변**이다.
  이유: `default()`는 감성 가중치 0.5를 전제하는데 이 슬라이스는 감성 중립이라 그 예산이
  사장되고, RSI 신호가 30~70 구간에서 0이어서(실측 94%) 도달 가능한 |score| 상한이 0.2 —
  임계 0.3에 **산술적으로 못 미쳐 스냅샷 814건이 전부 NEUTRAL이었다**(2026-07-30 발견).
  **하락은 방향으로 내지 않는다**(`down_threshold`를 도달 불가값으로 고정) — 재채점 2·3차 모두
  하락 방향은 2·3차에서 두 구간 연속 통과 조합이 없었다 — **4차(2026-08-28)에서 뒤집혔다**:
  적중을 변동성 초과로 재정의하고 하락 기준선을 따로 세우자 임계 -0.45가 홀드아웃 +8.8%p·
  인샘플 +5.1%p로 두 구간을 통과했다(-0.35·-0.50은 미달, 통과 구간 [-0.40,-0.45] 연속).
  옛 정의에서 막혔던 이유는 하락 기준선을 `1 − 상승기준선`(≈46%)으로 잡았기 때문이다.
  실측 하방 통계(낙폭·회복)는 방향 라벨과 함께 계속 병기한다.
  상세 → [[minseok/apps/stock/_docs/BACKTEST_RESCORE_2026-07|BACKTEST_RESCORE_2026-07]] 4차.
- **국면·하방·회복(2026-07-30)**: forecast 응답에 `position`(RSI 국면·60일 고점 대비 낙폭·
  지지선 여력, 순수 VO `PositionProfile` — 새 지표 계산 없이 기존 `Indicators`에서 파생)과
  `downside`(같은 신호 구간의 **장중 최대 낙폭** 중앙값·하위 25%·하락 마감 비율·**기준가 회복률**과
  회복 소요 일수)를 함께 낸다. `Backtester.distribution()`이 기존 워크포워드 루프 안에서
  마감 수익률과 함께 수집한다(루프 추가 없음). **회복률의 분모는 낙폭이 있었던 표본(`dip_samples`)뿐**
  — 무조정 상승일을 섞으면 회복률이 부풀려진다. 서사는 `forecast_narrator`의
  `position`·`downside`·`recovery` insight.
- **확률·예측 밴드(`stock_forecast` 슬라이스)**: `GET /stock/{symbol}/forecast?horizon=5` —
  저장 일봉 전체에 `Backtester.distribution()`(워크포워드, 감성 중립)을 돌려 **지금과 같은
  방향 신호가 났던 과거 평가일들의 상승 비율(확률)과 실현 수익률 분위수(25/50/75%)**를 반환.
  표본수·Wilson 95% 구간·기준선(평소 상승률)·`ready`(n≥100 + 하한>기준선) 동반, 같은 신호
  표본 30 미만이면 ATR 콘 폴백(`band.source: "atr"`). 인메모리 캐시(티커·horizon별, 마지막 봉
  ts 기준)로 일 1회만 재계산. **확률 노출 정책**: 실측 통계 + 표본·신뢰구간·기준선·"과거
  통계" 고지 병기 형태만 허용 — score 환산 등 근거 없는 확률 숫자 단독 노출 금지(기존 "확률
  제시 보류"의 해소 형태). chat 답변의 확률 단정 금지는 그대로 유지(페이지 전용).
- **레짐 조건화·어닝 veto(2026-07-22)**: forecast는 평가일마다 시장 레짐
  (`regime_calendar.py` — VIX>25면 HIGH_VOL 우선, 아니면 SPY 종가 vs 200일선로 BULL/BEAR,
  지수는 `collect_prices.py`의 INDEX_TICKERS로 1d만 수집)을 판정해 분포를 국면별로도 분할,
  현재 레짐 표본이 30 이상이면 조건부 통계·조건부 기준선을 쓴다(미달 시 무조건부 폴백,
  `regime_conditional` 표기). ready 게이트(n≥100+Wilson)는 선택된 슬라이스 위에서 불변.
  **한국 종목에도 SPY/VIX 레짐을 적용**(단순화 — 워치리스트 66/68이 미국). 어닝 veto:
  `EarningsCalendarPort`(yfinance `get_earnings_dates`, 일 1회 캐시, 실패 시 무-veto 열화)로
  발표 ±2캘린더일이면 방향을 관망 강등(`earnings_veto`) + 백테스트 평가일에서도 제외
  (벤더 제공 ~12분기 범위 내만). 오프라인 검증: `scripts/backtest_stock.py --regime --earnings-veto`.
- **감성 서프라이즈(2026-07-22)**: analyze의 감성 신호는 당일 절대값이 아니라
  **당일 LLM 값 − 최근 30일 라벨(news_labels) 평균** 편차로 투입한다(상시 긍정 종목의
  + 편향 상쇄). 기준선 표본 5건 미만·조회 실패면 기존 절대값 폴백(라벨 축적 초기 자연 열화).
  응답 `sentiment`는 원시값 유지, `sentiment_baseline`/`sentiment_surprise` 추가(additive —
  허브 계약·chat 무변경). 기준선 조회는 `NewsRepositoryPort.sentiment_baseline`.
- **예측 스냅샷·사후 채점(`forecast_snapshot` 슬라이스)**: 일일 cron(`scripts/snapshot_forecasts.py`,
  14:00, horizons 5·20)이 허브 `POST /automation/forecast-snapshots`(+`/score`)로 워치리스트
  forecast(방향·확률·밴드)와 신호 분해(breakdown)를 `forecast_snapshots` 테이블에 동결하고
  ((ticker, horizon_days, as_of) 유니크 — 재실행 멱등), horizon 도래분을 price_bars(1d)
  실현 수익률로 채점한다(UP→상승, DOWN→비상승 적중, NEUTRAL은 hit NULL — Backtester 의미론).
  캡처는 `StockForecastUseCase` 재사용 + market_data=None(라이브 폴백 차단, 미수집 종목 skip).
  **어느 조합으로 낸 판정인지 `signal_config`에 남긴다**(alembic `a1b2c3d4e5f7`) —
  **NULL 행은 2026-07-30 이전 `default()` 조합**(전량 NEUTRAL 구간)이라 이력을 섞어 읽으면 안 된다.
  같은 리비전이 재적합 피처(원시 `rsi`·`bb_percent_b`·`momentum_12_1`·`atr_pct` + 위치
  `drawdown_from_high_pct`·`above_support_pct`)와 하방 기대치(`trough_*`·`recovery_*`),
  채점 시 실측 `realized_trough_pct`(**구간 내 실제 장중 최저** — 마감가만으로는 "얼마나 빠졌다
  돌아왔나"를 사후에 물을 수 없다)를 함께 추가했다. 전부 nullable·백필 없음.
  요약(`summary`)은 방향·호라이즌·신호별(원신호 부호↔실현 수익률 부호 일치율) 적중률을 집계 —
  허브 `ForecastSnapshotPort`를 `ForecastSnapshotGateway`가 구현, admin `/admin/forecasts`가 소비.
  가중치 재적합·캘리브레이션의 원료 데이터 축(백테스트가 못 주는 진짜 out-of-sample 성적).
  **실행 시각 14:00 KST는 일봉 적재 시각에 맞춘 것**(2026-07-23 변경) — 세션 D의 일봉은
  D+1 13:05 KST에 들어오는데 기존 07:30은 그보다 6시간 일러, 매일 한 세션 묵은 봉으로
  as_of가 잡혔다(보드가 "기준 7/21"인데 가격은 7/22인 화면의 원인).
- **가중치 재적합·자동 승격(`forecast_refit` 슬라이스, 2026-08-21)**: 주 1회 배치
  (`scripts/refit_forecast_weights.py`, 토 15:00)가 허브 `POST /automation/forecast-refit`으로
  채점 완료 스냅샷의 **동결 원신호 × 실현 수익률**을 재채점한다(순수 도메인
  `weight_refit.py` — 후보 32조합 명시 열거, 저장된 `hit`은 옛 direction 기준이라 재사용
  금지, `realized_return_pct > 0`으로 재판정). 표본은 전 조합(NULL 포함 — 원신호는 config
  무관) · `earnings_veto` 제외. 게이트 = n≥100 + Wilson 95% 하한 > 기준선 + **현행 재채점
  하한 대비 마진 0.02**(히스테리시스) + 파라미터 동일 시 무승격(멱등). 통과 시
  `forecast_signal_configs`에 `refit-YYYYMMDD` 행을 활성으로 교체하고, 미달이어도
  `forecast_refit_reports`에 리포트를 남긴다(payload 정의처는 `RefitReport.to_payload()`).
  게이트는 5일 지평만 보고 20일은 참고 병기. `w_sentiment=0` 고정(감성 재적합은 ROADMAP
  E3의 몫) · 하락 임계는 검증값 `-0.45` 고정(스윕하지 않는다 — 하락 재적합은 스냅샷에 DOWN
  표본이 쌓인 뒤의 몫이다). 허브 `ForecastRefitPort`를
  `ForecastRefitGateway`가 구현, admin `/admin/forecast-refit`이 리더보드·조합 이력을 소비.
  승격 직후 채점 요약(`summary`)이 새 키 기준 0부터 재시작하는 것은 이력 분리의 의도된
  동작이다(구 키 미채점분 채점은 config 무관이라 계속 진행).
- **현재가 폴링(`stock_quote` 슬라이스)**: `GET /stock/{symbol}/quote` — `MarketDataPort.quote()`
  (yfinance fast_info, 이력 미조회)로 지연 시세 현재가만 경량 반환(`delayed: true`). 프론트
  30초 폴링용. 진짜 실시간은 KIS 등 벤더 어댑터 교체 경로(계약 동일)로 후속.
  포트 반환은 `Quote`(현재가 + 전일 종가) — 응답에 `previous_close`/`change_pct`를 함께 준다.
  봉을 함께 받지 않는 소비자(지수 스트립)도 등락률을 낼 수 있게 하기 위함이며, 벤더가 전일
  종가를 못 주면 둘 다 null로 열화한다.
- **신호 보드(`stock_board` 슬라이스)**: `GET /stock/board?horizon=5&limit=` — 워치리스트
  종목의 **최신 예측 스냅샷을 한 번에** 훑는 진입 화면(빈 워크스페이스)용 조회 전용 슬라이스.
  종목마다 analyze/forecast를 부르면 워치리스트 크기만큼 벤더 호출이 나므로 `forecast_snapshots`
  (일일 cron이 동결)만 읽는다 — `DISTINCT ON (ticker)` 최신 스냅샷 + `price_bars`(1d) 최근 30봉을
  윈도우 함수로 한 번에 받아 스파크라인·전일 대비를 만든다. 10일보다 오래된 스냅샷은 제외
  (워치리스트에서 빠진 종목의 옛 판정이 최신인 척 남는 것 방지). 정렬은 순수 도메인
  `board_ranker.sort_key` — **중립 후순위 → |score| 내림차순 → 티커순**으로, 매수 추천 순위가
  아니라 "신호가 뚜렷한 순"이다. 표시용 한글명은 `SymbolDirectoryPort`(`AliasSymbolDirectory` —
  `symbol_resolver`의 별칭 사전을 역인덱싱, 네트워크 조회 없음). 스냅샷이 없으면 404가 아니라
  빈 `rows`(수집 전에도 화면이 떠야 한다).
- **관심 보드 상태 제공(2026-08-23, ③-M7)**: 허브 `StockStatusPort`를 `StockStatusGateway`가
  구현 — 지정 심볼 집합의 최신 스냅샷+최근 종가 2봉을 일괄 조회해 recommendation의
  `/bookmarks/board`에 준다. stock_board와 같은 원칙(스냅샷만 읽기·10일 초과 제외)이며
  거래소 접미 변형(005930↔005930.KS)을 흡수한다. 스냅샷 없는 심볼은 결과에서 빠진다(열화).
- **신호 보드 제공(2026-09-03)**: 허브 `StockSignalBoardPort`를 `StockSignalBoardGateway`가
  구현 — `StockBoardUseCase.board()`를 지평 5·상한 limit으로 호출해 허브 DTO로 옮긴다(정렬·
  한글명 그대로). chat이 "상승 신호 나온 종목" 질문에 소비한다.
- **AI 모의투자(`paper` 슬라이스, 2026-09-08 — GAME_SUNSET_PAPER_TRADING_PLAN 3단계)**: 참가 계정 세 종류
  (`exaone`·`signal`·`user:<id>`)가 같은 원장 엔진을 탄다. **EXAONE 계정**은 하루 1회 `ExaoneDecisionAdapter`
  (오케스트레이터 `format="json"`·temperature 0)로 후보 ≤25종목(그날 스냅샷 + 3일 뉴스 라벨)·보유 포지션을
  읽고 JSON 주문을 낸다 — `decision_parser`가 후보 밖 종목·제시하지 않은 news_id·한도 위반을 **거부 사유와
  함께** 걸러낸다(환각 인용 차단). **지표 규칙 계정**은 `signal_rule_policy`(UP 롱·DOWN 숏·5거래일 청산·반대
  신호 조기 청산)가 결정론으로 판단하는 대조군. **사람 참가(주문)는 없다** — 2026-09-08 사용자 결정으로
  제거(체결 축이 달라 비교가 공정하지 않고, 사용자 14명이라 빈 타일만 남았다). 열람 전용이며 기준선은 SPY
  매수보유. AI 체결은 판단 다음 세션 **시가**. 규칙값은 전부
  `paper_rules.py`의 `assumed_*`(초기 1억·수수료 0.1%·환율 고정 1380·종목 ≤20%·≤10종목). 원장 산술은
  순수 `paper_ledger.py`(숏은 명목가 담보, 평가 `(2E−P)q`). 배치 `step(as_of)`은 체결 → 판단 채점(5거래일,
  스냅샷과 같은 `hit_unit` 정의, 숏 부호 반전) → 평가 → 판단 순서이며 **as_of 이후 봉·뉴스·스냅샷을 절대
  읽지 않는다**(`PaperFeedPort` 계약 — 리플레이가 라이브와 같은 코드 경로). 테이블 6개(`paper_*`, alembic
  `p5c6d7e8f9a0`). 매매 권유 문형 금지 — "어느 계정이 무엇을 샀다"까지만(사업자·신고 없음, 영구).

## 레이어

```
apps/stock/
├── domain/
│   ├── entities/{analysis_config,outlook}.py       # AnalysisConfig · Outlook(Direction)
│   ├── value_objects/{indicators,market_values,sentiment_score}.py
│   └── services/
│       ├── indicator_calculator.py                  # OHLC 시계열 → RSI/MA/지지·저항 (순수)
│       └── outlook_predictor.py                     # 지표+감성 → 방향/확신도 (순수)
├── app/
│   ├── dtos/stock_analysis_dto.py                   # StockAnalysis
│   ├── exceptions.py                                # StockError · MarketDataUnavailableError
│   ├── ports/input/stock_use_case.py
│   ├── ports/output/{market_data_port,sentiment_port}.py
│   └── use_cases/stock_interactor.py                # 대장
├── adapter/
│   ├── inbound/api/v1/stock_router.py               # POST /stock/analyze (앱 예외 → 404)
│   └── outbound/
│       ├── yfinance_market_data_adapter.py          # MarketDataPort 구현 (한국+미국)
│       ├── fake_market_data_adapter.py              # 테스트용 고정값
│       └── exaone_sentiment_adapter.py              # SentimentPort 구현 (오케스트레이터 경유)
├── dependencies/stock_provider.py
└── tests/                                           # 라이브 조회 테스트는 @pytest.mark.network
```

**의존 방향:** `adapter → app → domain`. 컨벤션 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].

## 신호 보드 감사 — 2026-09-17 (역추세 신호·자동 승격·하락 신호)

사용자 신고 "상승 신호 종목은 대부분 떨어지고, 하락 신호 종목은 대부분 오른다"에서 출발한 결정 기록.

- **신호의 뜻**: 판정은 RSI·볼린저 %B 평균회귀(역추세)가 주축이라 UP은 최근 하락해 과매도인 종목에 뜬다
  (9/1 조합 UP의 직전 5일 하락 비율 99%). 화면·채팅·알림 라벨을 "반등 신호/반등 후보"로 바꾸고 근거(RSI·%B),
  연속 일수(`signal_days`), 첫 신호 뒤 등락(`since_signal_pct`)을 보드에 싣는다 — UP 신호의 45%가 같은 종목 3일 내 반복.
- **자동 승격 중단·조합 복원**: 9/1 승격(RSI+BB 0.5/0.5, 모멘텀 0)은 7/20~8/31 표본에서 UP 적중 51.9%였지만 9월 17.8%
  (종목 기준선 25.1%). `forecast_signal_configs`에 `rollback-20260917`(시드 0.4/0.4/0.2, source=manual)을 활성화하고
  재적합 cron을 `--dry-run`으로 바꿨다. 시드는 같은 기간 UP 적중 45.8%/35.7%로 두 구간 모두 기준선 위.
- **재적합 게이트 개정**(`weight_refit`): 최근 14일은 선택에서 빼고 승자가 그 구간에서도 기준선을 넘어야 승격,
  n·적중률·Wilson은 종목×ISO 주 군집(실효 표본)으로 센다. 날짜 없는 표본은 표본 외 검증 불가로 승격하지 않는다.
- **하락 무발화 복귀(-1.01)**: 81종목(10년치 67종목) 2016-09~2021-09 / 2021-09~ 재검증에서 DOWN은 뒤 5년 우위
  시드 -1.0%p·RSI+BB -1.4%p(신호 뒤 5일 평균 +0.38%)로 미달. 8/28의 -0.45 검증은 16종목이었다.
  UP은 시드 +2.6/+0.9%p로 유지. 12-1 모멘텀 추세 필터는 시드 UP을 +2.5/+0.6%p로 개선하지 못해 미채택.
- **성적 감시**: `scripts/check_freshness.py`의 `signal_decay` — 매일 최근 14일 채점분을 판정 조합별 실효 표본으로 세어
  종목 기준선 이하면 메일 알림(옛 조합의 좋은 성적이 새 조합 부진을 가리지 않게 조합별 판정).
- **겹침 보정 재검증(같은 날 오후)**: 매일 평가한 5일 수익률 창은 겹쳐 독립 표본이 아니다. 유효 표본(÷5)으로 다시 채점하니
  활성 시드 UP 앞 +1.4%p·뒤 -0.2%p, 참고 신호(RSI+BB 0.5/0.5) 앞 +1.7%p·뒤 -0.5%p로 **최근 5년에서 어느 조합도 기준선을 넘지 못했다**.
  → 참고 신호 배지 노출 중단(`stock_interactor.REFERENCE_SIGNAL_ENABLED=False`, 계산식은 재검증용으로 유지),
  종목 예측의 ready·신뢰구간을 유효 표본으로(`backtest_report.overlap_effective`), 보드·모의투자 안내를 "검증되지 않은 참고 신호"로.
  신호 보드 자체를 유지할지는 제품 판단으로 남긴다.

## 위험 신호 보드 — 2026-09-17 재설계 (방향 → 변동성·낙폭)

감사 결론("최근 5년 어느 방향 조합도 기준선을 넘지 못함")에 대한 사용자 결정: 보드는 살리되 정확한 성능의 기능으로.
같은 83종목·같은 기준(~2020 학습 / 2021~ 검증, 20일 창 유효 표본 n/20, 두 구간 모두 95% 구간 분리)으로 대상을 바꿔 시험했다.

| 신호(향후 20거래일) | 조건 | 검증 구간 실측 |
|---|---|---|
| 변동성 확대 가능성 높음 | 20일 실현 변동성이 자기 1년 분포 상위 20% | 변동성이 자기 70분위 초과 51.3% vs 평소 32.6%(1.57배) |
| 변동성 확대 가능성 낮음 | 하위 20% | 17.1%(0.52배) |
| 큰 낙폭 위험 높음 | 고변동 + 200일선 아래 | 한 번이라도 -10% 하락 29.5% vs 24.3%(1.22배 — 약함) |
| 큰 낙폭 위험 낮음 | 저변동 + 50>200·가격>50 | 15.4%(0.63배) |

대조: 방향(추세 상승 → 20일 뒤 상승) 1.01배, 12-1 모멘텀 상·하위 스프레드 t=1.29 — 없음 재확인. 변동성 순위 월별 IC 0.74(68개월 전부 양수).

- **판정**: 순수 도메인 `domain/services/risk_signal.py` — 증분 계산(`states`)을 실시간 보드(`state_at`, 최근 300봉)와 주간 검증이 **같이** 쓴다.
  pandas 정의(rolling std·rank(pct)·quantile linear)와 값 일치를 테스트로 고정.
- **검증 리포트**: `scripts/backtest_risk_signal.py`(k8s CronJob `backtest-risk-signal`, 토 06:00, ~8초) → `risk_signal_reports`
  (alembic `r7e8f9a0b1c2`, payload 정의처 `risk_signal_backtester.py`). 검증 구간이 매주 최신 봉으로 늘어나며 두 구간 분리가 깨지면
  `validated=False` → 보드·채팅이 수치를 내린다(자동 강등만, 자동 승격 없음).
- **보드 API**: `GET /stock/board?order=risk`(기본) — 행에 `rv20·rv_percentile·vol_state·trend·drawdown_risk`, 응답에 `risk_stats`(상태별 검증 실측)·
  `risk_test_period`. 정렬 `board_ranker.risk_sort_key`(낙폭 위험 높음 → 변동성 높음 → 보통 → 낮음 → 판정 불가). `order=signal`은 옛 방향 순.
- **화면** `MarketBoard.tsx`: "오늘의 위험 신호 보드", 필터 전체/변동성·낙폭 주의/안정 구간, 행마다 위험 배지·변동성·1년 중 위치·검증 실측.
  방향 적중률 열은 뺐다. 위험 색은 destructive/brand — 가격 방향색(up 빨강·down 파랑)과 섞지 않는다.
- **채팅** `_answer_signal_board`: 방향을 물으면 "검증 미달이라 종목을 찍지 않는다"를 먼저, 주의·안정 그룹과 검증 실측. 종목 리포트에도 위험 신호 한 줄.
- **유지**: `forecast_snapshots`의 방향 판정·모의투자(지표 규칙 계정·EXAONE 후보)는 그대로 — 모의투자는 "검증되지 않은 참고 신호" 실험 기록.

## 신호 감시 개정 — 2026-09-18 (헛경보 정리 + 위험 신호 감시)

9/18 아침 알림이 **내린 조합을 채점해** 울렸다: 활성은 `rollback-20260917`인데 경보는 9/17에 내린 `refit-20260901`의
최근 14일 채점분(19군집·적중 1건, 5.3%)을 기준선 25.6%와 비교한 것이다. 1/19의 95% 구간은 1~26%라 기준선과 구별되지 않는다.
활성 조합은 채점분이 0건이었다(9/15~16 포착분은 5일 지평이라 ~9/22 채점).

- **활성 조합만 경보**(`signal_decay_verdict(..., active_config)`): 내린 조합 성적은 어드민 리포트로만 본다.
- **신뢰구간 판정**: `적중률 ≤ 기준선` → **95% Wilson 상한 < 기준선**, 군집 하한 15 → 30. 오늘 표본은 이 기준에서 울리지 않는다.
- **위험 신호 감시 신설**(`risk_signal_verdict`): 보드가 보여 주는 신호가 이번 주 검증에서 떨어지면(전주 validated → 이번 주 미달)
  또는 주간 리포트가 10일 넘게 낡으면 알린다. 화면은 수치를 조용히 내리기만 해서 사람이 몰랐다.
- **모의투자 지표 규칙 계정**: 표시명을 "지표 규칙(대조군)"으로, 설명을 "검증되지 않은 방향 신호를 그대로 따랐을 때"로 바꿨다.
  `market_view`의 "검증된 지표 규칙"은 사실과 달라 정정. 계정 자체는 유지 — 검증 안 된 신호를 따르면 어떻게 되는지가 이 계정의 값이다.

## 위험 규칙 모의투자 계정 — 2026-09-18 신설

"검증된 신호가 실제로 도움이 되는가"를 기록으로 남기는 세 번째 계정(`risk`, 표시명 "위험 규칙(검증 신호)").
지표 규칙 계정(`signal`)은 **검증되지 않은 방향 신호**를 따르는 대조군이고, 이 계정은 **검증된 위험 신호**만 쓴다.

- 규칙(`domain/services/risk_rule_policy.py`, 순수): `drawdown_risk == LOW`(저변동 + 50>200·가격>50일선)만 **롱**,
  5거래일 보유(대조군과 같은 지평), 보유 중 `HIGH`로 바뀌면 조기 청산, `earnings_veto` 진입 금지.
  같은 층에서는 변동성 백분위가 낮은 순 — 숏은 없다(하락을 맞히는 근거가 없다).
- 상태 판정은 보드·주간 검증과 **같은** `risk_signal.state_at`, 입력은 `PaperFeedPort.bars_until(as_of, 300)` —
  판단 시점 이후 봉을 보지 않아 리플레이가 라이브와 같은 원장을 만든다.
- 판단 근거 문구에 검증 실측을 적는다("검증 구간 20일 내 -10% 하락 15% vs 평소 24%").
- 화면: 성적표 4칸(AI 판단 · 지표 규칙(대조군) · 위험 규칙(검증 신호) · SPY), 자산 곡선에 한 줄 추가.
  chat 모의투자 답변도 세 계정을 함께 읽는다.
- 비교의 뜻: 위험 규칙 > 대조군이면 "검증된 위험 신호를 피하는 것이 도움이 된다"는 기록이 쌓이고, 아니면 그 반대다.
  어느 쪽이든 매매 권유가 아니라 기록이다.

## 위험 규칙 모의투자 계정 — 2026-09-18 신설

"검증된 신호가 실제로 도움이 되는가"를 기록으로 남기는 세 번째 계정(`risk`, 표시명 "위험 규칙(검증 신호)").
지표 규칙 계정(대조군)은 **검증되지 않은 방향 신호**를, 이 계정은 **검증 구간에서도 유지된 위험 신호**를 쓴다.

- 규칙(`domain/services/risk_rule_policy.py`, 순수): `drawdown_risk == LOW`(저변동 + 50>200·가격>50일선) 종목만 **롱**,
  5거래일 보유(대조군과 같은 지평), 보유 중 `HIGH` 전환이면 조기 청산, 실적 임박 진입 금지. 같은 층은 변동성 백분위 낮은 순.
  숏은 없다 — 하락을 맞히는 근거가 없다.
- 상태는 `PaperFeedPort.bars_until(as_of, 300)`으로 **판단 시점까지의 일봉만** 읽어 `risk_signal.state_at`으로 낸다
  (보드·주간 검증과 같은 함수, 리플레이 재현성 유지).
- 실측 미리보기(9/16 기준, 워치리스트 80): 낙폭 위험 낮음 6종목(SNDK·BRK-B·MU·TSM·MA·AMD), 높음 4·보통 70.
- 화면: 성적표 4칸(AI 판단 · 지표 규칙(대조군) · 위험 규칙(검증 신호) · SPY), 자산 곡선에 한 줄 추가. 채팅 모의투자 답변도 3계정.
- 비교의 뜻: 대조군과의 차이가 "검증된 위험 신호를 쓰면 달라지는가"의 관측치다. 표본이 쌓이기 전에는 성적을 결론으로 읽지 않는다.


## 종목 예측에 위험 신호 동반 — 2026-09-21

`GET /stock/{symbol}/forecast` 응답에 `risk`(변동성·낙폭 상태 + 지금 상태의 검증 실측)를 싣는다. 결론 한 줄
(프론트 `verdict.ts` · chat `verdict.py`)이 **중립일 때 위험 상태를 앞세우기 위한 재료**다 — 방향 판정의 73%가
중립이라 "지금은 방향을 말하기 어렵습니다"가 네 번 중 세 번 떴다(최근 30일 스냅샷 실측).

- 판정은 보드와 같은 `risk_signal.state_at(closes)` — forecast가 이미 전체 일봉을 들고 있어 추가 조회가 없다.
  봉이 모자라면(200일선·1년 분포 불가) `risk=None`.
- 실측은 최신 `risk_signal_reports`에서 **지금 상태에 해당하는 키만**(`risk_signal.stat_keys` — 낙폭이 변동성보다 먼저),
  그중 `validated`(학습·검증 두 구간 통과)만 싣는다. 상태가 보통이면 리포트를 읽지 않는다. 조회 실패는 상태만 싣는 열화.
- 포트: `RiskReportReadPort`(좁은 조회 포트)를 새로 두고 `StockBoardRepositoryPort`가 이를 상속한다 —
  forecast가 보드 저장소 전체를 알지 않게(ISP). 구현은 기존 `StockBoardPgRepository` 그대로.
- 허브 계약 `StockForecastSummary.risk`(`StockRiskSummary`)로 chat에도 같은 재료가 간다 — 채팅 카드와 페이지 결론이 같은 문장을 쓴다.

## 현재 감성은 저장 라벨 — 2026-09-21

종목 분석(`StockInteractor.analyze`)의 "뉴스 감성"이 질문마다 달랐다 — 같은 종목이 1분 사이 -0.20 → +0.10, 그 값이 방향 종합 점수에도
들어가 chat의 종목 비교 결론이 뒤집혔다(실대화 340). 원인 둘: ① 질문마다 헤드라인 묶음을 LLM에 새로 물었고(샘플링, 고정·재사용 없음)
② 프롬프트는 "소수 하나"인데 Gemma가 헤드라인마다 한 줄씩 숫자 목록을 돌려주는 일이 잦았고(배포 후 로그 3건 중 2건) 파서가 **첫 숫자만** 읽었다.

- 현재 감성 = 최근 `RECENT_SENTIMENT_DAYS`(7)일 **저장된 기사 라벨 평균**(`NewsRepositoryPort.sentiment_baseline(days=7)`, 기본 라벨러).
  표본이 `MIN_RECENT_SAMPLES`(3) 이상이면 LLM을 부르지 않는다 — 같은 시점이면 같은 값, 질문당 LLM 호출 1회 감소.
  서프라이즈(현재 − 30일 기준선)는 이제 양쪽이 같은 라벨러·같은 척도다. 라벨은 02:30 cron이 붙이므로 당일 수집 기사는 다음 날 반영된다.
- 라벨이 모자란 종목(미수집)만 LLM 폴백 — `temperature 0`, 응답의 -1~1 숫자 **전체 평균**으로 읽는다(`_parse_score`).

## 분석도 활성 검증 조합으로 판정 — 2026-09-21

`StockInteractor.analyze`가 코드 상수 `AnalysisConfig.default()`(검증 조합 0.8배 + **감성 0.2**, 상승 기준 0.28) 대신
예측·스냅샷과 같은 **활성 조합**(`SignalConfigPort.active()` — 현재 rollback-20260917: RSI 0.4·볼린저 0.4·모멘텀 0.2, 감성 0, 기준 0.35)을 읽는다.
조회 실패·포트 미주입은 생성자 조합(프로바이더는 `forecast_signal()`)으로 폴백.

- **왜**: 얹은 감성 서프라이즈(최근 7일 라벨 평균 − 30일 평균)를 화면이 쓰는 그대로 재검증하니 무신호였다 — 6/15~9/18, 81종목, 관측 4,475건:
  같은 날 두 종목 짝 비교 50.4%(5일)·50.1%(20일), 날짜별 순위상관 0.00·+0.04, 월별 부호가 바뀜(7월 −, 8월 0, 9월 +). EXAONE 라벨로도 같다(49.5%·49.0%).
  감성 **절대값**은 약한 역방향(47~49%, 상위 20% 초과수익이 하위보다 낮음 — 8/20 이벤트 연구와 같은 방향)이지만 화면은 절대값을 쓰지 않는다.
  한계: 촘촘한 뉴스가 2026-07~09 약 2.7개월뿐이라 "긴 기간 재검증"은 불가능하다 — 무신호인 것을 검증된 조합에 얹을 이유가 없다는 판단이다.
- **효과**: 같은 종목의 방향이 분석 화면과 예측에서 갈리던 원인 중 조합 쪽이 없어진다. 실측 12종목 중 1종목(035420)이 달라졌다 —
  기준선 없는 한국 종목이라 감성 절대값 +0.47이 그대로 얹혀 "상승"(+0.37/0.28)이던 것이 "중립"(+0.34/0.35)으로. 시세 원천(실시간 벤더 vs 수집 일봉) 차이는 남는다.
- 감성은 **참고 정보로 남는다**(값·라벨·헤드라인 표시, 기여도 막대는 가중치 0이라 회색 괄호). 서술 문장은 가중치가 0이면
  "반영했습니다"가 아니라 "방향 판정에는 넣지 않습니다"로 바뀐다(`stock_narrator`). 재적합이 감성을 검증해 활성 조합에 넣는 날이 오면 분석에도 자동으로 들어간다.
- n8n 시그널 스캔(배치 조립)도 같은 조합을 쓴다 — 감성만으로 넘던 알림이 줄어든다.

## 분석의 지표 입력 = 수집 일봉 · 감성 월례 채점 — 2026-09-21

**지표 입력**: `StockInteractor.analyze`가 질문마다 야후 2년 이력을 새로 받던 것을 **수집 일봉**(`ForecastHistoryPort.find_recent_daily_bars`, 최근 `ANALYZE_BARS`=520봉)
으로 바꿨다. 예측·스냅샷·검증이 전부 수집 일봉 기준인데 분석만 달라 같은 종목의 점수가 갈렸다 — 원인이 둘이었다:
① 장중엔 진행 중인 오늘 봉이 낀다(실측: 장중의 삼성전자 +0.14 vs -0.17) ② 야후는 배당을 소급 조정하고 수집분은 수집 시점 값이다(KO +0.27 vs +0.20, 장 마감 상태).
검증은 마감 일봉으로 했으므로 수집 일봉 쪽이 검증 조건이다. 바꾼 뒤 실측: 수집 종목 전부에서 분석 점수 = 최신 스냅샷 점수(KO +0.266 · 005930 +0.139 …), 소요 시간 약 절반.
520봉이면 전체 이력과 점수가 소수 넷째 자리까지 같다(12-1 모멘텀에 253봉). 현재가·등락률·헤드라인은 계속 실시간 벤더다.
폴백(벤더 이력): 미수집 종목 · 최신 봉이 `MAX_BAR_AGE`(7일)보다 낡음(수집 중단) · 봉 부족 · 조회 실패 · 포트 미주입 — 테스트가 다섯 갈래를 고정한다.

**감성 월례 채점**: 방향 점수에서 뺀 감성 서프라이즈를 되살릴지는 `domain/services/sentiment_signal_study.py`(순수)가 매달 채점한다 —
`scripts/study_news_events.py`가 같은 실행에서 함께 내고 리포트 payload `sentiment_surprise`에 싣는다. k8s CronJob `study-news-events`(매월 1일 07:00).
조건(전부): 표본 충분한 달(관측 200 이상) 6개 · 같은 날 짝 비교 적중 53% 이상 · 최근 6개월 중 5개월이 50% 초과. 넘으면 메일(check_freshness와 같은 창구),
넘기 전에는 가중치 0 유지. **결과를 보고 기준을 옮기지 않는다**(테스트가 상수를 고정). 첫 실행(9/21 dry-run): 5거래일 50.2%, 표본 충분한 달 4/6 — 유지.
촘촘한 뉴스가 2026-07부터라 6개월은 2027-01에 찬다. 과거 뉴스 소급(GDELT 등)은 라벨링 비용(10만 건 = 이 PC로 5일)·출처 차이 때문에 하지 않기로 했다.
