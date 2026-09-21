from datetime import UTC, datetime, timedelta

import pytest

from stock.app.dtos.stock_forecast_dto import ForecastQuery
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.use_cases import stock_forecast_interactor
from stock.app.use_cases.stock_forecast_interactor import StockForecastInteractor
from stock.domain.entities.outlook import Direction, Outlook
from stock.domain.entities.price_bar import PriceBar
from stock.domain.value_objects.forecast_distribution import (
    DirectionStats,
    ForecastDistribution,
)


def _bars(n: int, ticker: str = "TEST.KS") -> list[PriceBar]:
    """일 1% 단조 상승 합성봉 — 지표가 결정론적으로 나온다(전 평가일 NEUTRAL·전일 상승)."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    out = []
    price = 100.0
    for i in range(n):
        price *= 1.01
        out.append(PriceBar(
            ticker=ticker, timeframe="1d", ts=start + timedelta(days=i),
            open=price * 0.995, high=price * 1.005, low=price * 0.99,
            close=price, volume=1000,
        ))
    return out


class _StubPort:
    def __init__(self, bars, index_bars: dict[str, list] | None = None):
        self.bars = bars
        self.index_bars = index_bars or {}  # SPY/^VIX — 미수집(빈)이면 무레짐 폴백 경로
        self.full_loads = 0

    async def find_latest_daily_bar(self, symbol):
        if symbol in ("SPY", "^VIX"):
            series = self.index_bars.get(symbol, [])
            return series[-1] if series else None
        return self.bars[-1] if self.bars else None

    async def find_all_daily_bars(self, symbol):
        if symbol in ("SPY", "^VIX"):
            return self.index_bars.get(symbol, [])
        self.full_loads += 1
        return self.bars


@pytest.fixture(autouse=True)
def _clear_cache():
    stock_forecast_interactor._CACHE.clear()
    stock_forecast_interactor._LIVE_CACHE.clear()
    stock_forecast_interactor._REGIME_CACHE = None
    yield
    stock_forecast_interactor._CACHE.clear()
    stock_forecast_interactor._LIVE_CACHE.clear()
    stock_forecast_interactor._REGIME_CACHE = None


async def test_미보유_심볼이면_예외():
    with pytest.raises(MarketDataUnavailableError):
        await StockForecastInteractor(history=_StubPort([])).forecast(
            ForecastQuery(symbol="NOPE")
        )


async def test_봉이_부족하면_예외():
    with pytest.raises(MarketDataUnavailableError):
        await StockForecastInteractor(history=_StubPort(_bars(30))).forecast(
            ForecastQuery(symbol="TEST")
        )


async def test_상승_합성봉의_확률은_결정적이다():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(
        ForecastQuery(symbol="test")  # 소문자 입력도 정규화
    )
    assert view.symbol == "TEST"
    assert view.resolved_ticker == "TEST.KS"
    assert view.horizon_days == 5
    # 단조 상승 합성봉은 RSI 100 + 밴드 상단 — 8/28~9/16엔 하락 신호였지만 2026-09-17 하락 무발화 복귀로 관망이다.
    # 관망은 방향 주장이 아니므로 확률은 유의 판정을 하지 않는다(ready False 고정).
    assert view.signal_direction == "NEUTRAL"
    p = view.probability
    assert p is not None
    assert p.ready is False
    assert any(i.key == "probability" for i in view.insights)
    assert any(i.key == "basis" for i in view.insights)


async def test_표본_30_이상이면_분위수_밴드():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.band.source == "quantile"
    # 일 1% × 5거래일 ≈ +5.1% — 분위수 전부 그 근방
    assert 0.045 < view.band.median_pct < 0.055
    assert view.band.q25_pct <= view.band.median_pct <= view.band.q75_pct


async def test_표본_부족이면_ATR_콘_폴백():
    view = await StockForecastInteractor(history=_StubPort(_bars(70))).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.band.source == "atr"
    assert view.band.median_pct == 0.0
    assert view.band.q75_pct == -view.band.q25_pct > 0
    assert any(i.key == "band" and "변동성" in i.text for i in view.insights)


async def test_같은_날은_캐시로_재계산하지_않는다():
    port = _StubPort(_bars(120))
    interactor = StockForecastInteractor(history=port)
    first = await interactor.forecast(ForecastQuery(symbol="TEST"))
    second = await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert first is second
    assert port.full_loads == 1  # 캐시 히트면 일봉 풀로드도 생략(마지막 봉 1행만 조회)


class _StubSignalConfigs:
    """활성 조합 스텁 — key를 바꿔 재적합 승격을 흉내낸다."""

    def __init__(self, key: str = "forecast_signal"):
        from stock.domain.entities.analysis_config import AnalysisConfig
        self.key = key
        self.config = AnalysisConfig.forecast_signal()

    async def active(self):
        from stock.app.dtos.signal_config_dto import ActiveSignalConfig
        return ActiveSignalConfig(key=self.key, config=self.config)

    async def activate(self, key, config):  # pragma: no cover - 미사용
        raise NotImplementedError

    async def history(self):  # pragma: no cover - 미사용
        raise NotImplementedError


async def test_조합_키가_바뀌면_캐시가_무효화된다():
    """재적합 승격(활성 키 교체)이 다음 요청부터 즉시 반영돼야 한다 — 캐시 키에 조합 키 포함."""
    port = _StubPort(_bars(120))
    configs = _StubSignalConfigs(key="forecast_signal")
    interactor = StockForecastInteractor(history=port, configs=configs)
    await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert port.full_loads == 1

    configs.key = "refit-20260905"  # 승격 — 파라미터가 같아도 키가 다르면 재계산
    await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert port.full_loads == 2


async def test_DOWN_신호는_하락_적중률이_하락_기준선을_이겨야_유의하다(monkeypatch):
    """2026-08-28 규칙 변경 — 하락은 '상승률이 낮다'가 아니라 '하락 적중이 잦다'로 잰다.

    변동성 문턱을 쓰면 결과가 셋(초과 상승 / 초과 하락 / 잡음)이라 (1 − 상승기준선)이
    하락 기준선이 아니다. 그래서 하락도 상승과 같은 모양 — 하한 > 그 방향 기준선 — 이 된다.
    """
    interactor = StockForecastInteractor(history=_StubPort(_bars(120)))
    monkeypatch.setattr(
        interactor._predictor, "predict",
        lambda *a, **k: Outlook(direction=Direction.DOWN, confidence=0.5),
    )
    # 하락 적중 45%(450/1000) vs 하락 기준선 30% — 우위 +15%p. 겹침 보정(÷5일) 뒤 유효 표본 200 ≥ 100
    down = DirectionStats(1000, 200, -0.02, -0.01, 0.0, down_hits=450)
    dist = ForecastDistribution(
        horizon_days=5, evaluated=400, baseline_up_rate=0.55, baseline_down_rate=0.30,
        by_direction={
            "UP": DirectionStats(0, 0, None, None, None),
            "DOWN": down,
            "NEUTRAL": DirectionStats(200, 110, 0.0, 0.0, 0.0),
        },
    )
    monkeypatch.setattr(interactor._backtester, "distribution", lambda *a, **k: dist)

    view = await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert view.signal_direction == "DOWN"
    p = view.probability
    assert p.hits == 450 and p.up_rate == 0.45     # 방향 적중률
    assert p.baseline_up_rate == 0.30              # 그 방향의 기준선
    assert p.ready is True
    assert not any(i.key == "sample" for i in view.insights)  # 참고용 경고 없음


async def test_원표본_200은_겹침_보정하면_유효_40이라_유의하지_않다(monkeypatch):
    """2026-09-17 — 매일 평가한 5일 창은 겹친다. 같은 45% vs 30%라도 원표본 200은 독립 표본 40개 수준이다."""
    interactor = StockForecastInteractor(history=_StubPort(_bars(120)))
    monkeypatch.setattr(
        interactor._predictor, "predict",
        lambda *a, **k: Outlook(direction=Direction.DOWN, confidence=0.5),
    )
    down = DirectionStats(200, 40, -0.02, -0.01, 0.0, down_hits=90)
    dist = ForecastDistribution(
        horizon_days=5, evaluated=400, baseline_up_rate=0.55, baseline_down_rate=0.30,
        by_direction={
            "UP": DirectionStats(0, 0, None, None, None),
            "DOWN": down,
            "NEUTRAL": DirectionStats(200, 110, 0.0, 0.0, 0.0),
        },
    )
    monkeypatch.setattr(interactor._backtester, "distribution", lambda *a, **k: dist)
    view = await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert view.probability.ready is False and view.probability.sample_size == 200


async def test_DOWN은_상승률이_낮다는_이유만으로는_유의하지_않다(monkeypatch):
    """옛 규칙(ci_high < 상승기준선)이었다면 통과했을 표본 — 이제는 떨어져야 한다."""
    interactor = StockForecastInteractor(history=_StubPort(_bars(120)))
    monkeypatch.setattr(
        interactor._predictor, "predict",
        lambda *a, **k: Outlook(direction=Direction.DOWN, confidence=0.5),
    )
    # 상승은 35%로 기준선 55%보다 뚜렷이 낮지만, 하락 적중은 25%로 기준선 30%에 못 미친다
    # (나머지 40%는 잡음 구간 — 오르지도 내리지도 않은 날)
    down = DirectionStats(200, 70, -0.02, -0.01, 0.0, down_hits=50)
    dist = ForecastDistribution(
        horizon_days=5, evaluated=400, baseline_up_rate=0.55, baseline_down_rate=0.30,
        by_direction={
            "UP": DirectionStats(0, 0, None, None, None),
            "DOWN": down,
            "NEUTRAL": DirectionStats(200, 110, 0.0, 0.0, 0.0),
        },
    )
    monkeypatch.setattr(interactor._backtester, "distribution", lambda *a, **k: dist)

    view = await interactor.forecast(ForecastQuery(symbol="TEST"))
    assert view.probability.ready is False


async def test_ready_기준은_표본과_신뢰구간_하한():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(
        ForecastQuery(symbol="TEST")
    )
    # 표본 64회(<100) → ready False + 참고용 경고 문장
    assert view.probability.ready is False
    assert any(i.key == "sample" and i.tone == "warning" for i in view.insights)


class _StubMarketData:
    def __init__(self, bars):
        self.bars = bars
        self.calls = 0

    async def daily_bars(self, symbol):
        self.calls += 1
        return self.bars


async def test_미수집_종목은_라이브_이력으로_계산한다():
    view = await StockForecastInteractor(
        history=_StubPort([]), market_data=_StubMarketData(_bars(120, ticker="RKLB")),
    ).forecast(ForecastQuery(symbol="RKLB"))
    assert view.live is True
    assert view.resolved_ticker == "RKLB"
    assert view.band is not None


async def test_수집_봉이_있으면_라이브를_쓰지_않는다():
    view = await StockForecastInteractor(
        history=_StubPort(_bars(120)), market_data=_StubMarketData([]),
    ).forecast(ForecastQuery(symbol="TEST"))
    assert view.live is False


async def test_라이브는_같은_날_재요청에_벤더를_다시_부르지_않는다():
    market = _StubMarketData(_bars(120, ticker="RKLB"))
    interactor = StockForecastInteractor(history=_StubPort([]), market_data=market)
    first = await interactor.forecast(ForecastQuery(symbol="RKLB"))
    second = await interactor.forecast(ForecastQuery(symbol="RKLB"))
    assert first is second
    assert market.calls == 1  # 일 단위 라이브 캐시 — 2y 다운로드는 하루 1회


# ---- 레짐 조건화 · 어닝 veto ----

def _spy_bars(end_ts: datetime, n: int, close: float = 100.0) -> list[PriceBar]:
    """종목 마지막 봉과 같은 날 끝나는 지수 합성봉 — 상수 종가라 항상 BEAR(종가 == MA)."""
    return [
        PriceBar(
            ticker="SPY", timeframe="1d", ts=end_ts - timedelta(days=n - 1 - i),
            open=close, high=close + 1, low=close - 1, close=close, volume=0,
        )
        for i in range(n)
    ]


class _StubEarnings:
    def __init__(self, dates):
        self.dates = dates

    async def earnings_dates(self, symbol):
        return self.dates


async def test_레짐_표본_충분하면_조건부_통계():
    bars = _bars(120)
    spy = _spy_bars(bars[-1].ts, 600)  # 평가 구간 전체에 MA200 형성 → 전 평가일 BEAR
    view = await StockForecastInteractor(
        history=_StubPort(bars, index_bars={"SPY": spy})
    ).forecast(ForecastQuery(symbol="TEST"))
    assert view.regime == "BEAR"
    assert view.regime_conditional is True  # 전 평가일이 같은 레짐 — 표본 = 무조건부와 동일
    assert any(i.key == "regime" for i in view.insights)


async def test_레짐_표본_부족하면_무조건부_폴백():
    bars = _bars(120)
    # MA200이 마지막 5일에만 형성 — 현재 레짐은 있으나 조건부 표본 < 30
    spy = _spy_bars(bars[-1].ts, 204)
    view = await StockForecastInteractor(
        history=_StubPort(bars, index_bars={"SPY": spy})
    ).forecast(ForecastQuery(symbol="TEST"))
    assert view.regime == "BEAR"
    assert view.regime_conditional is False


async def test_지수_미수집이면_무레짐():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.regime is None and view.regime_conditional is False


async def test_어닝_임박이면_관망_강등():
    bars = _bars(120)
    view = await StockForecastInteractor(
        history=_StubPort(bars),
        earnings=_StubEarnings([bars[-1].ts.date() + timedelta(days=1)]),  # 내일 발표 → ±2일 안
    ).forecast(ForecastQuery(symbol="TEST"))
    assert view.earnings_veto is True
    assert view.signal_direction == "NEUTRAL"
    assert any(i.key == "earnings" for i in view.insights)


async def test_어닝_멀면_veto_없음():
    bars = _bars(120)
    view = await StockForecastInteractor(
        history=_StubPort(bars),
        earnings=_StubEarnings([bars[-1].ts.date() + timedelta(days=30)]),
    ).forecast(ForecastQuery(symbol="TEST"))
    assert view.earnings_veto is False


async def test_어닝_포트_없으면_기존_동작():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.earnings_veto is False


# --- 위험 신호(2026-09-21) — 결론 한 줄이 중립일 때 앞세울 재료 ---

class _StubRiskReports:
    def __init__(self, payload: dict | None = None, broken: bool = False):
        self.payload = payload
        self.broken = broken
        self.calls = 0

    async def find_latest_risk_report(self):
        self.calls += 1
        if self.broken:
            raise RuntimeError("db down")
        return (datetime(2026, 9, 20, tzinfo=UTC), self.payload) if self.payload is not None else None


def _signal(key: str, rate: float, base: float, validated: bool) -> dict:
    return {"key": key, "test": {"rate": rate, "base": base}, "validated": validated}


def _risk_state(vol: str, drop: str):
    from stock.domain.services.risk_signal import RiskState

    return RiskState(rv20=0.42, rv_percentile=0.91, vol_state=vol, trend="DOWN", drawdown_risk=drop, rv_q70=0.3)


async def test_위험_상태와_검증을_통과한_실측만_싣는다(monkeypatch):
    monkeypatch.setattr(stock_forecast_interactor.risk_signal, "state_at", lambda closes: _risk_state("HIGH", "HIGH"))
    reports = _StubRiskReports({"signals": [
        _signal("vol_high", 0.51, 0.33, True),
        _signal("drop_high", 0.30, 0.24, False),  # 검증 미통과 — 수치를 말하면 안 된다
    ]})
    view = await StockForecastInteractor(history=_StubPort(_bars(120)), risk_reports=reports).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.risk is not None
    assert (view.risk.vol_state, view.risk.drawdown_risk, view.risk.trend) == ("HIGH", "HIGH", "DOWN")
    assert view.risk.rv_percentile == 0.91
    assert [(e.key, e.test_rate, e.base_rate) for e in view.risk.evidence] == [("vol_high", 0.51, 0.33)]


async def test_위험_상태가_보통이면_리포트를_읽지_않는다(monkeypatch):
    monkeypatch.setattr(stock_forecast_interactor.risk_signal, "state_at", lambda closes: _risk_state("NORMAL", "NORMAL"))
    reports = _StubRiskReports({"signals": [_signal("vol_high", 0.51, 0.33, True)]})
    view = await StockForecastInteractor(history=_StubPort(_bars(120)), risk_reports=reports).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.risk is not None and view.risk.evidence == ()
    assert reports.calls == 0


@pytest.mark.parametrize("reports", [None, _StubRiskReports(None), _StubRiskReports(broken=True)],
                         ids=["포트 없음", "리포트 없음", "조회 실패"])
async def test_리포트를_못_읽어도_상태는_싣는다(monkeypatch, reports):
    monkeypatch.setattr(stock_forecast_interactor.risk_signal, "state_at", lambda closes: _risk_state("HIGH", "NORMAL"))
    view = await StockForecastInteractor(history=_StubPort(_bars(120)), risk_reports=reports).forecast(
        ForecastQuery(symbol="TEST")
    )
    assert view.risk is not None and view.risk.vol_state == "HIGH"
    assert view.risk.evidence == ()


async def test_봉이_모자라_위험_판정이_안_되면_risk는_없다():
    view = await StockForecastInteractor(history=_StubPort(_bars(120))).forecast(ForecastQuery(symbol="TEST"))
    assert view.risk is None  # 위험 판정은 200일선·1년 분포가 필요하다(120봉으로는 불가)
