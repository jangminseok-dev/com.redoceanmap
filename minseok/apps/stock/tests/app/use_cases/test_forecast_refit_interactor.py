"""ForecastRefitInteractor — 표본 수집 규칙·승격/미달/dry-run 분기를 스텁 포트로 검증."""
from datetime import UTC, datetime

from stock.app.dtos.forecast_refit_dto import RefitReportView
from stock.app.dtos.signal_config_dto import ActiveSignalConfig
from stock.app.use_cases.forecast_refit_interactor import ForecastRefitInteractor
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.forecast_snapshot import ForecastSnapshot
from stock.domain.value_objects.signal_breakdown import SignalContribution

AS_OF = datetime(2026, 7, 1, tzinfo=UTC)


def _signals(rsi: float = 0.0, bollinger: float = 0.0) -> tuple[SignalContribution, ...]:
    return tuple(
        SignalContribution(key=key, signal=value, weight=0.0, contribution=0.0)
        for key, value in (
            ("sentiment", 0.0), ("rsi", rsi), ("trend", 0.0),
            ("bollinger", bollinger), ("obv", 0.0), ("momentum", 0.0),
        )
    )


def _scored(
    snapshot_id: int, horizon: int = 5, rsi: float = 0.0, bollinger: float = 0.0,
    ret: float | None = 0.01, earnings_veto: bool = False,
) -> ForecastSnapshot:
    return ForecastSnapshot(
        id=snapshot_id, ticker="TEST.KS", as_of=AS_OF, horizon_days=horizon,
        direction="NEUTRAL", base_price=100.0, score=0.0,
        signals=_signals(rsi=rsi, bollinger=bollinger),
        evaluated_at=datetime(2026, 7, 10, tzinfo=UTC),
        realized_return_pct=ret, earnings_veto=earnings_veto,
    )


def _promotable_snapshots() -> list[ForecastSnapshot]:
    """현행(임계 0.35)이 놓치는 강신호 고적중 120건 + 무신호 하락 200건 — 게이트 통과 표본."""
    strong = [
        _scored(i, rsi=0.4, bollinger=0.4, ret=0.02 if i < 110 else -0.02)
        for i in range(120)
    ]
    noise = [_scored(1000 + i, ret=-0.02) for i in range(200)]
    return strong + noise


class _StubSnapshots:
    def __init__(self, by_horizon: dict[int, list[ForecastSnapshot]]):
        self.by_horizon = by_horizon
        self.asked: list[int] = []

    async def find_scored_all(self, horizon):
        self.asked.append(horizon)
        return self.by_horizon.get(horizon, [])


class _StubConfigs:
    def __init__(self):
        self.activated: list[tuple[str, AnalysisConfig]] = []
        self.rows = ["seed-row"]

    async def active(self):
        return ActiveSignalConfig(key="forecast_signal", config=AnalysisConfig.forecast_signal())

    async def activate(self, key, config):
        self.activated.append((key, config))

    async def history(self):
        return self.rows


class _StubReports:
    def __init__(self, latest=None):
        self.saved: list[tuple[dict, dict]] = []
        self._latest = latest

    async def save(self, params, payload):
        self.saved.append((params, payload))

    async def latest(self):
        return self._latest


def _interactor(snapshots, configs=None, reports=None) -> ForecastRefitInteractor:
    return ForecastRefitInteractor(
        snapshots=snapshots, configs=configs or _StubConfigs(), reports=reports or _StubReports()
    )


async def test_게이트_통과시_자동_승격하고_리포트를_남긴다():
    configs, reports = _StubConfigs(), _StubReports()
    result = await _interactor(
        _StubSnapshots({5: _promotable_snapshots()}), configs, reports
    ).run(promote=True)

    assert result.promoted is True
    assert result.activated_key.startswith("refit-") and len(result.activated_key) <= 24
    [(key, config)] = configs.activated
    assert key == result.activated_key
    assert config.down_threshold == -1.01 and config.w_sentiment == 0.0
    [(params, payload)] = reports.saved
    assert params["activated_key"] == result.activated_key
    assert payload["promote"] is True


async def test_게이트_미달이면_리포트만_남긴다():
    configs, reports = _StubConfigs(), _StubReports()
    few = [_scored(i, rsi=0.4, bollinger=0.4, ret=0.02) for i in range(30)]
    result = await _interactor(_StubSnapshots({5: few}), configs, reports).run(promote=True)

    assert result.promoted is False and result.activated_key is None
    assert configs.activated == []
    [(params, payload)] = reports.saved  # 미달 리포트도 저장 — 표본 축적 경과 관측
    assert params["activated_key"] is None
    assert payload["promote"] is False
    assert result.reasons  # 왜 미달인지 남는다


async def test_dry_run이면_게이트를_통과해도_승격하지_않는다():
    configs, reports = _StubConfigs(), _StubReports()
    result = await _interactor(
        _StubSnapshots({5: _promotable_snapshots()}), configs, reports
    ).run(promote=False)

    assert result.promoted is False
    assert configs.activated == []
    [(params, payload)] = reports.saved
    assert params["promote"] is False
    assert payload["promote"] is True  # 판정 자체는 "통과"로 기록된다(승격만 생략)


async def test_표본_규칙_veto와_미채점은_빠지고_두_지평을_묻는다():
    snapshots = _StubSnapshots({
        5: [
            _scored(1, rsi=0.4, bollinger=0.4, ret=0.02),
            _scored(2, rsi=0.4, bollinger=0.4, ret=0.02, earnings_veto=True),  # 제외
            _scored(3, rsi=0.4, bollinger=0.4, ret=None),                      # 제외
        ],
    })
    reports = _StubReports()
    await _interactor(snapshots, reports=reports).run(promote=True)

    assert sorted(snapshots.asked) == [5, 20]
    [(params, _)] = reports.saved
    assert params["samples"] == {"5": 1, "20": 0}


async def test_latest와_config_history는_위임한다():
    view = RefitReportView(ran_at=AS_OF, params={}, payload={})
    configs = _StubConfigs()
    interactor = _interactor(_StubSnapshots({}), configs, _StubReports(latest=view))
    assert await interactor.latest() is view
    assert await interactor.config_history() == ["seed-row"]
