import pytest

from stock.app.dtos.stock_analysis_dto import StockAnalysis
from stock.app.use_cases.stock_interactor import StockInteractor
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.market_values import Price, Symbol
from stock.domain.value_objects.sentiment_score import SentimentScore


class _StubMarketData:
    async def latest_price(self, symbol):
        return Price(225.0)

    async def indicators(self, symbol):
        return Indicators(rsi=58.0, ma20=222.0, ma50=210.0, support=205.0, resistance=235.0)

    async def recent_headlines(self, symbol):
        return ["strong earnings", "price target raised"]


class _StubSentiment:
    async def analyze(self, headlines):
        return SentimentScore(0.7)


async def test_analyze_returns_structured_analysis_without_trade_rec():
    interactor = StockInteractor(
        market_data=_StubMarketData(),
        sentiment=_StubSentiment(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.default(),
    )
    result = await interactor.analyze(Symbol("AAPL"))

    assert isinstance(result, StockAnalysis)
    assert result.symbol == "AAPL"
    assert result.direction in {"UP", "DOWN", "NEUTRAL"}
    assert result.support == 205.0 and result.resistance == 235.0
    assert result.headlines == ["strong earnings", "price target raised"]
    # 신규 지표 노출 — 스텁 Indicators는 기본값이라 중립값 그대로 내려온다.
    assert result.atr_pct == 0.0 and result.bb_percent_b == 0.5
    assert result.volume_ratio == 1.0 and result.obv_slope == 0.0
    assert result.momentum_12_1 == 0.0
    assert result.reference_up_signal is False  # rsi 58·%B 0.5 — 참고 신호 조건 미달
    # 매매 추천이 아니라 방향 전망만 — 주문/수량 필드가 없다.
    assert not hasattr(result, "ordered")


class _OversoldMarketData(_StubMarketData):
    async def indicators(self, symbol):
        # 과매도 + 밴드 하단 — 참고 신호(RSI+BB ±0.35) 발화 조건
        return Indicators(
            rsi=15.0, ma20=222.0, ma50=210.0, support=205.0, resistance=235.0, bb_percent_b=0.0,
        )


async def test_참고_신호는_재검증_미달로_과매도_밴드하단이어도_꺼져_있다():
    interactor = StockInteractor(
        market_data=_OversoldMarketData(),
        sentiment=_StubSentiment(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.default(),
    )
    result = await interactor.analyze(Symbol("AAPL"))

    assert result.reference_up_signal is False  # 2026-09-17 겹침 보정 재검증 미달 — REFERENCE_SIGNAL_ENABLED=False
    # 참고 신호는 본 판정(기본 config + 감성)을 오염시키지 않는다.
    assert result.direction in {"UP", "DOWN", "NEUTRAL"}
    assert result.sentiment == 0.7


class _StubDemand:
    def __init__(self, fail=False):
        self.fail = fail
        self.recorded: list[str] = []

    async def record(self, ticker):
        if self.fail:
            raise RuntimeError("DB down")
        self.recorded.append(ticker)


async def test_분석_시_수요를_기록한다():
    demand = _StubDemand()
    interactor = StockInteractor(
        market_data=_StubMarketData(),
        sentiment=_StubSentiment(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.default(),
        demand=demand,
    )
    await interactor.analyze(Symbol("AAPL"))
    assert demand.recorded == ["AAPL"]


async def test_수요_기록_실패는_분석에_영향_없다():
    interactor = StockInteractor(
        market_data=_StubMarketData(),
        sentiment=_StubSentiment(),
        predictor=OutlookPredictor(),
        config=AnalysisConfig.default(),
        demand=_StubDemand(fail=True),
    )
    result = await interactor.analyze(Symbol("AAPL"))
    assert result.price == 225.0  # 기록 실패에도 분석은 정상 반환


class _StubNewsWithBaseline:
    """감성 기준선 스텁 — recent_titles는 빈 리스트(벤더 헤드라인만 쓰게)."""

    def __init__(self, avg, n, recent=None, recent_n=0):
        self.avg = avg
        self.n = n
        self.recent = recent        # 최근 7일 창(현재 감성) — 기본은 라벨 없음(LLM 폴백 경로)
        self.recent_n = recent_n

    async def recent_titles(self, query, ticker="", limit=5):
        return []

    async def sentiment_baseline(self, ticker, days=30):
        return (self.avg, self.n) if days >= 30 else (self.recent, self.recent_n)


async def test_기준선_충분하면_서프라이즈가_신호에_들어간다():
    # 당일 0.7, 30일 평균 0.6 → 서프라이즈 +0.1 — 상시 긍정 종목의 + 편향이 걸러진다
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=_StubSentiment(),
        predictor=OutlookPredictor(), config=AnalysisConfig.default(),
        news=_StubNewsWithBaseline(avg=0.6, n=12),
    )
    result = await interactor.analyze(Symbol("AAPL"))

    assert result.sentiment == 0.7                       # 노출 값은 원시 당일값 유지
    assert result.sentiment_baseline == 0.6
    assert result.sentiment_surprise == pytest.approx(0.1)
    sentiment_signal = next(c for c in result.signals if c.key == "sentiment")
    assert sentiment_signal.signal == pytest.approx(0.1)  # 신호에는 편차가 들어간다
    assert any(i.key == "sentiment_surprise" for i in result.insights)


async def test_기준선_표본_부족이면_절대값_폴백():
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=_StubSentiment(),
        predictor=OutlookPredictor(), config=AnalysisConfig.default(),
        news=_StubNewsWithBaseline(avg=0.6, n=3),  # < MIN_BASELINE_SAMPLES(5)
    )
    result = await interactor.analyze(Symbol("AAPL"))

    assert result.sentiment_baseline is None
    assert result.sentiment_surprise is None
    sentiment_signal = next(c for c in result.signals if c.key == "sentiment")
    assert sentiment_signal.signal == pytest.approx(0.7)  # 기존 동작
    assert not any(i.key == "sentiment_surprise" for i in result.insights)


async def test_기준선_조회_실패는_절대값_폴백():
    class _Broken(_StubNewsWithBaseline):
        async def sentiment_baseline(self, ticker, days=30):
            raise RuntimeError("DB down")

    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=_StubSentiment(),
        predictor=OutlookPredictor(), config=AnalysisConfig.default(),
        news=_Broken(avg=None, n=0),
    )
    result = await interactor.analyze(Symbol("AAPL"))
    assert result.sentiment_surprise is None
    assert result.sentiment == 0.7


class _CountingSentiment:
    def __init__(self):
        self.calls = 0

    async def analyze(self, headlines):
        self.calls += 1
        return SentimentScore(0.7)


async def test_현재_감성은_저장된_최근_라벨_평균이고_LLM을_부르지_않는다():
    """2026-09-21: 질문마다 LLM에 물으니 같은 종목이 1분 사이에 -0.20 → +0.10으로 바뀌어 종목 비교 결론이 뒤집혔다."""
    llm = _CountingSentiment()
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=llm, predictor=OutlookPredictor(), config=AnalysisConfig.default(),
        news=_StubNewsWithBaseline(avg=0.10, n=40, recent=0.25, recent_n=9),
    )
    first = await interactor.analyze(Symbol("AAPL"))
    second = await interactor.analyze(Symbol("AAPL"))
    assert first.sentiment == second.sentiment == 0.25     # 같은 시점이면 같은 값
    assert first.sentiment_surprise == pytest.approx(0.15)  # 최근 7일 − 30일 기준선(같은 라벨러·같은 척도)
    assert llm.calls == 0


async def test_최근_라벨이_모자라면_LLM_폴백():
    llm = _CountingSentiment()
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=llm, predictor=OutlookPredictor(), config=AnalysisConfig.default(),
        news=_StubNewsWithBaseline(avg=0.10, n=40, recent=0.9, recent_n=2),   # < MIN_RECENT_SAMPLES(3)
    )
    result = await interactor.analyze(Symbol("AAPL"))
    assert result.sentiment == 0.7 and llm.calls == 1


# --- 2026-09-21: 분석도 예측과 같은 활성 검증 조합으로 판정한다 ---

class _StubConfigs:
    def __init__(self, config=None, broken=False):
        self.config = config
        self.broken = broken

    async def active(self):
        from stock.app.dtos.signal_config_dto import ActiveSignalConfig

        if self.broken:
            raise RuntimeError("db down")
        return ActiveSignalConfig(key="active-test", config=self.config)


async def test_분석은_활성_검증_조합으로_판정하고_감성은_점수에_들어가지_않는다():
    """분석만 코드 상수(검증 조합 0.8배 + 감성 0.2)를 써서 같은 종목이 분석 화면과 예측에서 방향이 갈렸고,
    얹은 감성 서프라이즈는 재검증에서 무신호였다(짝 비교 49~50%, 월마다 부호가 바뀜)."""
    def build(sentiment_value):
        class _S:
            async def analyze(self, headlines):
                return SentimentScore(sentiment_value)
        return StockInteractor(
            market_data=_StubMarketData(), sentiment=_S(), predictor=OutlookPredictor(),
            config=AnalysisConfig.default(), configs=_StubConfigs(AnalysisConfig.forecast_signal()),
        )

    gloomy = await build(-1.0).analyze(Symbol("AAPL"))
    rosy = await build(1.0).analyze(Symbol("AAPL"))
    # 뉴스가 극단으로 달라도 점수·방향·기준은 같다 — 감성은 참고 정보로만 남는다
    assert gloomy.score == rosy.score and gloomy.direction == rosy.direction
    assert rosy.up_threshold == AnalysisConfig.forecast_signal().up_threshold == 0.35
    assert (gloomy.sentiment, rosy.sentiment) == (-1.0, 1.0)
    sentiment_signal = next(c for c in rosy.signals if c.key == "sentiment")
    assert sentiment_signal.weight == 0 and sentiment_signal.contribution == 0


async def test_활성_조합을_못_읽으면_생성자_조합으로_폴백한다():
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=_StubSentiment(), predictor=OutlookPredictor(),
        config=AnalysisConfig.forecast_signal(), configs=_StubConfigs(broken=True),
    )
    result = await interactor.analyze(Symbol("AAPL"))
    assert result.up_threshold == 0.35   # 조회 실패에도 분석은 나간다


async def test_감성_가중치가_0이면_반영했다고_말하지_않는다():
    interactor = StockInteractor(
        market_data=_StubMarketData(), sentiment=_StubSentiment(), predictor=OutlookPredictor(),
        config=AnalysisConfig.default(), configs=_StubConfigs(AnalysisConfig.forecast_signal()),
        news=_StubNewsWithBaseline(avg=0.6, n=12),
    )
    result = await interactor.analyze(Symbol("AAPL"))
    text = next(i.text for i in result.insights if i.key == "sentiment_surprise")
    assert "방향 판정에는 넣지 않습니다" in text and "반영했습니다" not in text


# --- 2026-09-21: 분석의 지표 입력 = 수집 일봉(예측과 같은 입력) ---

def _collected_bars(n=300, last_age_days=1, drift=1.002):
    from datetime import UTC, datetime, timedelta

    from stock.domain.entities.price_bar import PriceBar

    end = datetime.now(UTC) - timedelta(days=last_age_days)
    out, price = [], 100.0
    for i in range(n):
        price *= drift
        out.append(PriceBar(ticker="AAPL", timeframe="1d", ts=end - timedelta(days=n - 1 - i),
                            open=price * 0.99, high=price * 1.01, low=price * 0.98, close=price, volume=1_000_000))
    return out


class _StubHistory:
    def __init__(self, bars=None, broken=False):
        self.bars = bars or []
        self.broken = broken
        self.limits: list[int] = []

    async def find_recent_daily_bars(self, symbol, limit):
        self.limits.append(limit)
        if self.broken:
            raise RuntimeError("db down")
        return self.bars[-limit:]


class _CountingMarketData(_StubMarketData):
    def __init__(self):
        self.indicator_calls = 0

    async def indicators(self, symbol):
        self.indicator_calls += 1
        return await super().indicators(symbol)


def _interactor(market, history):
    return StockInteractor(market_data=market, sentiment=_StubSentiment(), predictor=OutlookPredictor(),
                           config=AnalysisConfig.forecast_signal(), history=history)


async def test_수집_일봉이_있으면_그_봉으로_지표를_계산하고_벤더_이력을_받지_않는다():
    """분석만 질문마다 야후 2년 이력을 받아 장중 진행 봉·배당 조정 차이로 예측과 점수가 달랐다(삼성전자 +0.14 vs -0.17)."""
    from stock.domain.services.indicator_calculator import IndicatorCalculator

    bars = _collected_bars()
    market, history = _CountingMarketData(), _StubHistory(bars)
    result = await _interactor(market, history).analyze(Symbol("AAPL"))
    expected = IndicatorCalculator().compute([b.close for b in bars], [b.low for b in bars], [b.high for b in bars],
                                             [float(b.volume) for b in bars])
    assert market.indicator_calls == 0 and history.limits == [520]
    assert result.rsi == expected.rsi and result.ma20 == expected.ma20   # 예측이 쓰는 계산기·같은 입력
    assert result.price == 225.0                                          # 현재가는 여전히 실시간 시세


@pytest.mark.parametrize("history", [
    _StubHistory([]),                                   # 미수집 종목
    _StubHistory(_collected_bars(last_age_days=9)),     # 수집이 멈춰 최신 봉이 7일 넘게 낡음
    _StubHistory(_collected_bars(n=30)),                # 봉이 모자라 지표 계산 불가
    _StubHistory(broken=True),                          # 조회 실패
    None,                                               # 포트 미주입(구 조립)
], ids=["미수집", "낡은 봉", "봉 부족", "조회 실패", "포트 없음"])
async def test_수집_일봉을_못_쓰면_시세_벤더로_폴백한다(history):
    market = _CountingMarketData()
    result = await _interactor(market, history).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 1 and result.price == 225.0


# --- 2026-09-21: 수집이 아직 담지 못한 마감 봉은 벤더 이력에서 보충한다 ---

class _VendorBarsMarketData(_CountingMarketData):
    """daily_bars를 주는 시세 벤더 — 현재가 조회 때 이미 받아 둔 이력(어댑터 캐시)에 해당한다."""

    def __init__(self, vendor_bars=None, broken=False):
        super().__init__()
        self.vendor_bars = vendor_bars or []
        self.broken = broken

    async def daily_bars(self, symbol):
        if self.broken:
            raise RuntimeError("yahoo down")
        return self.vendor_bars


def _next_bar(last, *, hours_ago, close):
    from datetime import UTC, datetime, timedelta

    from stock.domain.entities.price_bar import PriceBar

    ts = datetime.now(UTC) - timedelta(hours=hours_ago)
    assert ts > last.ts
    return PriceBar(ticker="AAPL", timeframe="1d", ts=ts, open=close, high=close * 1.01, low=close * 0.99,
                    close=close, volume=1_000_000)


def _expected(bars):
    from stock.domain.services.indicator_calculator import IndicatorCalculator

    return IndicatorCalculator().compute([b.close for b in bars], [b.low for b in bars], [b.high for b in bars],
                                         [float(b.volume) for b in bars])


async def test_수집보다_새로운_마감_봉은_벤더_이력에서_보충한다():
    bars = _collected_bars(last_age_days=2)
    closed = _next_bar(bars[-1], hours_ago=20, close=bars[-1].close * 0.9)   # 시작 + 17시간이 지난 봉 — 마감
    market = _VendorBarsMarketData([*bars, closed])
    result = await _interactor(market, _StubHistory(bars)).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 0
    assert result.rsi == _expected([*bars, closed]).rsi != _expected(bars).rsi


async def test_진행_중인_봉은_보충하지_않는다():
    """검증 조건은 마감 일봉이다 — 장중 봉이 끼면 분석과 예측의 점수가 다시 갈린다."""
    bars = _collected_bars(last_age_days=2)
    open_bar = _next_bar(bars[-1], hours_ago=5, close=bars[-1].close * 0.9)
    market = _VendorBarsMarketData([*bars, open_bar])
    result = await _interactor(market, _StubHistory(bars)).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 0 and result.rsi == _expected(bars).rsi


async def test_가격_기준이_어긋나면_벤더_이력으로_계산한다():
    """수집에는 액면분할 처리가 없다 — 분할 전 가격에 분할 후 봉을 이어 붙이면 지표가 망가진다."""
    from dataclasses import replace

    bars = _collected_bars(last_age_days=2)
    split = [replace(b, close=b.close / 10) for b in bars]   # 벤더는 1:10 분할을 소급 반영
    market = _VendorBarsMarketData([*split, _next_bar(bars[-1], hours_ago=20, close=bars[-1].close / 10)])
    await _interactor(market, _StubHistory(bars)).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 1


async def test_배당_소급_조정_수준의_차이는_기준_불일치가_아니다():
    from dataclasses import replace

    bars = _collected_bars(last_age_days=2)
    adjusted = [replace(b, close=b.close * 0.97) for b in bars]   # 실측 최대 괴리 2.9%
    market = _VendorBarsMarketData(adjusted)
    await _interactor(market, _StubHistory(bars)).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 0


async def test_보충에_실패하면_수집분만으로_계산한다():
    bars = _collected_bars()
    market = _VendorBarsMarketData(broken=True)
    result = await _interactor(market, _StubHistory(bars)).analyze(Symbol("AAPL"))
    assert market.indicator_calls == 0 and result.rsi == _expected(bars).rsi
