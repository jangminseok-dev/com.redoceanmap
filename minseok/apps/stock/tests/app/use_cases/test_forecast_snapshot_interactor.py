from datetime import UTC, datetime, timedelta

import pytest

from stock.app.dtos.forecast_snapshot_dto import CaptureCommand
from stock.app.dtos.stock_forecast_dto import (
    BandInfo,
    DownsideInfo,
    ProbabilityInfo,
    StockForecastView,
)
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.use_cases.forecast_snapshot_interactor import ForecastSnapshotInteractor
from stock.domain.entities.forecast_snapshot import ForecastSnapshot
from stock.domain.entities.price_bar import PriceBar
from stock.domain.value_objects.position_profile import PositionProfile
from stock.domain.value_objects.signal_breakdown import SignalContribution

AS_OF = datetime(2026, 7, 1, tzinfo=UTC)


def _bars(n: int, ticker: str = "TEST.KS") -> list[PriceBar]:
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


def _view(symbol: str, horizon: int, direction: str = "UP", with_prob: bool = True,
          regime: str | None = None, earnings_veto: bool = False,
          with_position: bool = True) -> StockForecastView:
    return StockForecastView(
        symbol=symbol, resolved_ticker=f"{symbol}.KS", as_of=AS_OF,
        base_price=100.0, horizon_days=horizon, signal_direction=direction,
        probability=ProbabilityInfo(
            up_rate=0.6, sample_size=120, hits=72, ci_low=0.51, ci_high=0.68,
            baseline_up_rate=0.5, ready=True,
        ) if with_prob else None,
        band=BandInfo(source="quantile", q25_pct=-0.01, median_pct=0.005, q75_pct=0.02),
        insights=[],
        position=PositionProfile(
            rsi=28.0, rsi_zone="oversold", drawdown_from_high_pct=-0.12,
            above_support_pct=0.03, atr_pct=0.02,
        ) if with_position else None,
        downside=DownsideInfo(
            trough_median_pct=-0.03, trough_q25_pct=-0.07, down_close_rate=0.4,
            dip_samples=90, recovery_rate=0.6, recovery_days_median=3.0,
        ) if with_position else None,
        regime=regime, regime_conditional=regime is not None, earnings_veto=earnings_veto,
    )


def _snapshot(
    snapshot_id: int, ticker: str = "TEST.KS", direction: str = "UP", horizon: int = 5,
    as_of: datetime = AS_OF, base_price: float = 100.0, signals: tuple = (),
    evaluated: bool = False, realized_return_pct: float | None = None, hit: bool | None = None,
    signal_config: str | None = "forecast_signal",
) -> ForecastSnapshot:
    return ForecastSnapshot(
        id=snapshot_id, ticker=ticker, as_of=as_of, horizon_days=horizon,
        direction=direction, base_price=base_price, score=0.4, signals=signals,
        evaluated_at=datetime(2026, 7, 10, tzinfo=UTC) if evaluated else None,
        realized_return_pct=realized_return_pct, hit=hit,
        signal_config=signal_config,
    )


class _StubForecaster:
    def __init__(self, views: dict[tuple[str, int], StockForecastView]):
        self.views = views
        self.calls: list[tuple[str, int]] = []

    async def forecast(self, query):
        self.calls.append((query.symbol, query.horizon))
        key = (query.symbol, query.horizon)
        if key not in self.views:
            raise MarketDataUnavailableError(query.symbol)
        return self.views[key]


class _StubHistory:
    def __init__(self, bars_by_symbol: dict[str, list[PriceBar]]):
        self.bars_by_symbol = bars_by_symbol
        self.loads = 0

    async def find_latest_daily_bar(self, symbol):
        bars = self.bars_by_symbol.get(symbol, [])
        return bars[-1] if bars else None

    async def find_all_daily_bars(self, symbol):
        self.loads += 1
        return self.bars_by_symbol.get(symbol, [])


class _StubRepo:
    def __init__(self, pending: list[ForecastSnapshot] | None = None,
                 scored: list[ForecastSnapshot] | None = None):
        self.saved: list[ForecastSnapshot] = []
        self.pending = pending or []
        self.scored = scored or []
        self.applied = []
        self.asked_configs: list[str | None] = []  # 집계가 조합을 좁혀 물었는지 검증용

    async def save_many(self, snapshots):
        self.saved.extend(snapshots)
        return len(snapshots)

    async def find_pending(self):
        return self.pending

    async def apply_scores(self, updates):
        self.applied.extend(updates)
        return len(updates)

    async def find_scored(self, horizon, limit, signal_config=None):
        self.asked_configs.append(signal_config)
        return [s for s in self.scored if self._match(s, horizon, signal_config)][:limit]

    async def find_recent(self, horizon, limit, signal_config=None):
        return ([s for s in self.pending + self.scored
                 if self._match(s, horizon, signal_config)][:limit])

    @staticmethod
    def _match(s, horizon, signal_config) -> bool:
        return ((horizon is None or s.horizon_days == horizon)
                and (signal_config is None or s.signal_config == signal_config))

    async def counts(self, horizon, signal_config=None):
        both = self.pending + self.scored
        pool = [s for s in both if self._match(s, horizon, signal_config)]
        return len(pool), len([s for s in pool if s.evaluated_at is not None])


class _StubSignalConfigs:
    """활성 조합 스텁 — 재적합 승격 후의 키를 흉내낸다."""

    def __init__(self, key: str):
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


def _interactor(forecaster, history, repo, configs=None) -> ForecastSnapshotInteractor:
    return ForecastSnapshotInteractor(
        forecaster=forecaster, history=history, snapshots=repo, configs=configs
    )


async def test_capture_maps_view_and_breakdown():
    bars = _bars(60)
    forecaster = _StubForecaster({("TEST", 5): _view("TEST", 5), ("TEST", 20): _view("TEST", 20)})
    repo = _StubRepo()
    result = await _interactor(forecaster, _StubHistory({"TEST": bars}), repo).capture(
        CaptureCommand(tickers=["test"], horizons=[5, 20])
    )

    assert result.captured == 2 and result.skipped == []
    assert {s.horizon_days for s in repo.saved} == {5, 20}
    snap = repo.saved[0]
    assert snap.ticker == "TEST.KS"          # resolved_ticker 정본
    assert snap.as_of == AS_OF
    assert snap.up_rate == 0.6 and snap.ready is True
    assert snap.band_source == "quantile"
    # 신호 분해 6종 동결 + 합산 점수 일치
    assert [c.key for c in snap.signals] == [
        "sentiment", "rsi", "trend", "bollinger", "obv", "momentum",
    ]
    assert snap.score == pytest.approx(sum(c.contribution for c in snap.signals))
    # 어느 조합으로 낸 판정인지 남는다 — NULL은 2026-07-30 이전 default() 조합이라는 뜻이므로
    # 신규 캡처가 이 값을 비우면 이력이 조용히 섞인다
    assert snap.signal_config == "forecast_signal"
    # 원시 지표는 signals(정규화값)에서 복원할 수 없어 별도로 동결한다
    assert snap.bb_percent_b is not None and snap.momentum_12_1 is not None


async def test_capture_freezes_position_and_downside():
    """뷰의 국면·하방 통계가 스냅샷에 동결돼야 사후 오답 분석이 가능하다."""
    bars = _bars(60)
    view = _view("TEST", 5)
    forecaster = _StubForecaster({("TEST", 5): view})
    repo = _StubRepo()
    await _interactor(forecaster, _StubHistory({"TEST": bars}), repo).capture(
        CaptureCommand(tickers=["TEST"], horizons=[5])
    )

    snap = repo.saved[0]
    assert snap.rsi == pytest.approx(view.position.rsi)
    assert snap.drawdown_from_high_pct == pytest.approx(view.position.drawdown_from_high_pct)
    assert snap.above_support_pct == pytest.approx(view.position.above_support_pct)
    assert snap.trough_median_pct == pytest.approx(view.downside.trough_median_pct)
    assert snap.recovery_rate == pytest.approx(view.downside.recovery_rate)


async def test_capture_tolerates_view_without_position():
    """구 뷰(국면·하방 없음)로도 캡처가 죽지 않는다 — 필드는 NULL로 남는다."""
    bars = _bars(60)
    forecaster = _StubForecaster({("TEST", 5): _view("TEST", 5, with_position=False)})
    repo = _StubRepo()
    await _interactor(forecaster, _StubHistory({"TEST": bars}), repo).capture(
        CaptureCommand(tickers=["TEST"], horizons=[5])
    )

    snap = repo.saved[0]
    assert snap.rsi is None and snap.trough_median_pct is None
    assert snap.signal_config == "forecast_signal"  # 조합 식별자는 뷰와 무관하게 남는다


async def test_capture_probability_none_and_breakdown_once_per_ticker():
    bars = _bars(60)
    forecaster = _StubForecaster({
        ("TEST", 5): _view("TEST", 5, with_prob=False),
        ("TEST", 20): _view("TEST", 20, with_prob=False),
    })
    history = _StubHistory({"TEST": bars})
    repo = _StubRepo()
    await _interactor(forecaster, history, repo).capture(
        CaptureCommand(tickers=["TEST"], horizons=[5, 20])
    )

    assert history.loads == 1  # breakdown용 봉 로드는 티커당 1회
    assert all(s.up_rate is None and s.ready is False for s in repo.saved)


async def test_capture_skips_uncollected_ticker():
    forecaster = _StubForecaster({("TEST", 5): _view("TEST", 5)})
    repo = _StubRepo()
    result = await _interactor(
        forecaster, _StubHistory({"TEST": _bars(60)}), repo
    ).capture(CaptureCommand(tickers=["TEST", "GHOST"], horizons=[5]))

    assert result.captured == 1
    assert result.skipped == ["GHOST"]


async def test_score_up_down_neutral_and_pending():
    signals = ()
    # as_of 이후 5봉: 종가 100→96 (하락) — TEST.KS 봉
    down_bars = _bars(60)
    future = []
    price = 96.0
    for i in range(5):
        future.append(PriceBar(
            ticker="TEST.KS", timeframe="1d", ts=AS_OF + timedelta(days=i + 1),
            open=price, high=price + 1, low=price - 1, close=price, volume=1000,
        ))
    bars = [b for b in down_bars if b.ts <= AS_OF] + future

    pending = [
        _snapshot(1, direction="UP", signals=signals),       # ret<0 → hit=False
        _snapshot(2, direction="DOWN", signals=signals),     # ret<=0 → hit=True
        _snapshot(3, direction="NEUTRAL", signals=signals),  # hit=None
        _snapshot(4, direction="UP", horizon=20, signals=signals),  # 봉 부족 → 미채점
    ]
    repo = _StubRepo(pending=pending)
    result = await _interactor(
        _StubForecaster({}), _StubHistory({"TEST.KS": bars}), repo
    ).score()

    assert result.scored == 3 and result.pending == 1
    by_id = {u.snapshot_id: u for u in repo.applied}
    assert by_id[1].hit is False
    assert by_id[2].hit is True
    assert by_id[3].hit is None
    assert 4 not in by_id
    assert by_id[1].realized_price == pytest.approx(96.0)
    assert by_id[1].realized_return_pct == pytest.approx(-0.04)
    # 마감가(-4%)보다 장중 저가(95)가 더 낮았다 — 오답이 얼마나 나쁘게 틀렸는지의 재료
    assert by_id[1].realized_trough_pct == pytest.approx(-0.05)


async def test_summary_aggregates_and_signal_definition():
    sig_up = SignalContribution(key="rsi", signal=0.5, weight=0.3, contribution=0.15)
    sig_down = SignalContribution(key="bollinger", signal=-0.4, weight=0.0, contribution=0.0)
    sig_zero = SignalContribution(key="obv", signal=0.0, weight=0.0, contribution=0.0)
    scored = [
        _snapshot(1, direction="UP", evaluated=True, realized_return_pct=0.03, hit=True,
                  signals=(sig_up, sig_zero)),
        _snapshot(2, direction="UP", evaluated=True, realized_return_pct=-0.02, hit=False,
                  signals=(sig_up,)),
        _snapshot(3, direction="NEUTRAL", evaluated=True, realized_return_pct=-0.01, hit=None,
                  signals=(sig_down,)),
    ]
    repo = _StubRepo(scored=scored)
    view = await _interactor(_StubForecaster({}), _StubHistory({}), repo).summary(
        horizon=None, recent_limit=10
    )

    assert view.kpi.scored == 3 and view.kpi.pending == 0
    assert view.kpi.hit_rate == pytest.approx(0.5)      # NEUTRAL 제외 1/2
    assert view.kpi.up_hit_rate == pytest.approx(0.5)
    assert view.kpi.down_hit_rate is None               # DOWN 표본 없음
    # by_signal: rsi n=2(+0.03 적중·-0.02 실패), bollinger n=1(신호<0·ret<=0 적중), obv 제외
    by_key = {s.key: s for s in view.by_signal}
    assert by_key["rsi"].n == 2 and by_key["rsi"].hits == 1
    assert by_key["bollinger"].n == 1 and by_key["bollinger"].hits == 1
    assert "obv" not in by_key
    directions = {d.direction: d for d in view.by_direction}
    assert directions["NEUTRAL"].hit_rate is None
    assert directions["NEUTRAL"].avg_realized_return_pct == pytest.approx(-0.01)


async def test_summary_empty_returns_none_rates():
    repo = _StubRepo()
    view = await _interactor(_StubForecaster({}), _StubHistory({}), repo).summary(
        horizon=5, recent_limit=10
    )
    assert view.kpi.total == 0
    assert view.kpi.hit_rate is None
    assert view.by_horizon == [] and view.by_signal == []


async def test_capture_freezes_regime_and_earnings_veto():
    forecaster = _StubForecaster({
        ("TEST", 5): _view("TEST", 5, regime="BEAR", earnings_veto=True),
    })
    repo = _StubRepo()
    await _interactor(forecaster, _StubHistory({"TEST": _bars(60)}), repo).capture(
        CaptureCommand(tickers=["TEST"], horizons=[5])
    )
    snap = repo.saved[0]
    assert snap.regime == "BEAR"
    assert snap.regime_conditional is True
    assert snap.earnings_veto is True


async def test_summary_by_regime_groups_null_as_none():
    scored = [
        _snapshot(1, direction="UP", evaluated=True, realized_return_pct=0.02, hit=True),
        _snapshot(2, direction="UP", evaluated=True, realized_return_pct=-0.01, hit=False),
    ]
    object.__setattr__(scored[0], "regime", "BULL")  # frozen 우회 — 테스트 픽스처 편의
    repo = _StubRepo(scored=scored)
    view = await _interactor(_StubForecaster({}), _StubHistory({}), repo).summary(
        horizon=None, recent_limit=10
    )
    regimes = {r.regime: r for r in view.by_regime}
    assert regimes["BULL"].scored == 1 and regimes["BULL"].hit_rate == 1.0
    assert regimes["NONE"].scored == 1 and regimes["NONE"].hit_rate == 0.0


async def test_summary_excludes_previous_signal_config():
    """구 조합(signal_config NULL) 판정은 집계에서 빠진다.

    규칙이 다른 판정을 한 분모에 넣으면 적중률·신호 일치율이 서로 다른 성적의 합이 된다.
    특히 by_signal은 hit이 아니라 실현 수익률 부호로 계산해 구 조합 채점분이 그대로 섞인다
    (구 조합은 전량 NEUTRAL이라 hit_rate에는 안 섞였다 — 그래서 조용히 틀렸다).
    """
    scored = [
        _snapshot(1, direction="UP", evaluated=True, realized_return_pct=0.02, hit=True),
        # 구 조합 — 같은 UP·같은 채점이지만 다른 규칙의 판정
        _snapshot(2, direction="UP", evaluated=True, realized_return_pct=-0.05, hit=False,
                  signal_config=None),
    ]
    repo = _StubRepo(scored=scored)
    view = await _interactor(_StubForecaster({}), _StubHistory({}), repo).summary(
        horizon=None, recent_limit=10
    )

    assert repo.asked_configs == ["forecast_signal"]  # 조합을 좁혀 물었는지
    assert view.kpi.scored == 1 and view.kpi.hit_rate == 1.0  # 구 조합 오답이 섞이면 0.5가 된다
    assert view.by_direction[0].avg_realized_return_pct == pytest.approx(0.02)
    assert [r.ticker for r in view.recent] == ["TEST.KS"] and len(view.recent) == 1


async def test_capture_stamps_active_config_key():
    """재적합 승격 뒤 캡처는 새 활성 키를 스탬프한다 — 이력이 조합별로 갈린다."""
    forecaster = _StubForecaster({("TEST", 5): _view("TEST", 5)})
    repo = _StubRepo()
    await _interactor(
        forecaster, _StubHistory({"TEST": _bars(60)}), repo,
        configs=_StubSignalConfigs(key="refit-20260905"),
    ).capture(CaptureCommand(tickers=["TEST"], horizons=[5]))
    assert repo.saved[0].signal_config == "refit-20260905"


async def test_summary_narrows_by_active_config_key():
    """요약 집계도 활성 키 기준 — 승격 직후 0부터 재시작하는 것이 의도된 동작이다."""
    scored = [
        _snapshot(1, direction="UP", evaluated=True, realized_return_pct=0.02, hit=True,
                  signal_config="refit-20260905"),
        _snapshot(2, direction="UP", evaluated=True, realized_return_pct=-0.05, hit=False),
    ]
    repo = _StubRepo(scored=scored)
    view = await _interactor(
        _StubForecaster({}), _StubHistory({}), repo,
        configs=_StubSignalConfigs(key="refit-20260905"),
    ).summary(horizon=None, recent_limit=10)
    assert repo.asked_configs == ["refit-20260905"]
    assert view.kpi.scored == 1 and view.kpi.hit_rate == 1.0
