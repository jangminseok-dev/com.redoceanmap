from datetime import UTC, datetime

from admin.app.use_cases.analytics_interactor import AnalyticsInteractor
from hub.app.dtos.area_backtest_report_dto import AreaBacktestReportInfo
from hub.app.dtos.forecast_snapshot_dto import AccuracyKpi, ForecastAccuracyReport


def _report() -> ForecastAccuracyReport:
    return ForecastAccuracyReport(
        kpi=AccuracyKpi(total=10, scored=4, pending=6,
                        hit_rate=0.5, up_hit_rate=0.5, down_hit_rate=None),
        by_horizon=[], by_direction=[], by_regime=[], by_signal=[], recent=[],
    )


class _StubForecastPort:
    def __init__(self):
        self.args = None

    async def capture(self, tickers, horizons):  # pragma: no cover - 미사용
        raise NotImplementedError

    async def score(self):  # pragma: no cover - 미사용
        raise NotImplementedError

    async def accuracy_report(self, horizon, recent_limit):
        self.args = (horizon, recent_limit)
        return _report()


class _StubEventStudyPort:
    def __init__(self, report=None):
        self.report = report

    async def latest(self):
        return self.report


class _StubBacktestPort:
    def __init__(self, info=None):
        self.info = info

    async def latest(self):
        return self.info


class _StubRefitPort:
    def __init__(self, report=None, history=None):
        self.report = report
        self.history = history or []

    async def run(self, promote):  # pragma: no cover - 미사용
        raise NotImplementedError

    async def latest(self):
        return self.report

    async def config_history(self):
        return self.history


def _interactor(
    forecasts=None, area_backtests=None, news_events=None, refits=None
) -> AnalyticsInteractor:
    return AnalyticsInteractor(
        forecasts=forecasts or _StubForecastPort(),
        area_backtests=area_backtests or _StubBacktestPort(),
        news_events=news_events or _StubEventStudyPort(),
        refits=refits or _StubRefitPort(),
    )


async def test_forecast_report_delegates_with_args():
    port = _StubForecastPort()
    result = await _interactor(forecasts=port).forecast_report(horizon=5, limit=30)
    assert port.args == (5, 30)
    assert result.report.kpi.total == 10


async def test_market_backtest_none_when_no_run():
    result = await _interactor(area_backtests=_StubBacktestPort(info=None)).market_backtest_report()
    assert result.report is None


async def test_market_backtest_passthrough():
    info = AreaBacktestReportInfo(
        ran_at=datetime(2026, 7, 22, tzinfo=UTC), params={"quarters": "20192-20253"},
        n_observations=100, n_areas=50, base_quarters=[20192],
        grade_outcomes=[], component_predictiveness=[],
    )
    result = await _interactor(area_backtests=_StubBacktestPort(info=info)).market_backtest_report()
    assert result.report is info


async def test_뉴스_이벤트_연구_실행_이력이_없으면_None():
    assert (await _interactor(
        news_events=_StubEventStudyPort(report=None)
    ).news_event_study()).report is None


async def test_뉴스_이벤트_연구_리포트를_그대로_전달한다():
    sentinel = object()
    assert (await _interactor(
        news_events=_StubEventStudyPort(report=sentinel)
    ).news_event_study()).report is sentinel


async def test_재적합_리포트와_조합_이력을_한_응답에_담는다():
    report, history = object(), [object()]
    result = await _interactor(
        refits=_StubRefitPort(report=report, history=history)
    ).forecast_refit()
    assert result.report is report
    assert result.history == history


async def test_재적합_실행_이력이_없으면_report_None_이력은_유지():
    seed = object()  # 시드 조합은 실행 전에도 이력에 있다
    result = await _interactor(refits=_StubRefitPort(report=None, history=[seed])).forecast_refit()
    assert result.report is None
    assert result.history == [seed]
