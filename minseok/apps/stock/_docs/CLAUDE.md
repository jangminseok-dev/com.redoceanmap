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
  하락 방향은 두 구간 연속 통과 조합이 없었다. 대신 실측 하방 통계로 답한다(아래).
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
  E3의 몫) · 하락 무발화(`down_threshold=-1.01`) 유지. 허브 `ForecastRefitPort`를
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
