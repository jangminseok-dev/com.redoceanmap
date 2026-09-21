from __future__ import annotations

from hub.app.dtos.stock_forecast_dto import StockForecastSummary, StockRiskEvidence, StockRiskSummary
from hub.app.ports.output.stock_forecast_port import StockForecastPort
from stock.app.dtos.stock_forecast_dto import ForecastQuery
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_forecast_use_case import StockForecastUseCase


class StockForecastGateway(StockForecastPort):
    """허브 StockForecastPort 구현 — 이미 해석된 종목 코드로 stock forecast 유스케이스에 위임한다.

    chat이 결론 한 줄에 쓸 확률 요약만 추린다(밴드·인사이트는 페이지 전용이라 제외).
    수집 일봉이 없어 산출 불가하면 None으로 열화(chat은 표본 없음 결론으로 처리).
    """

    def __init__(self, use_case: StockForecastUseCase) -> None:
        self._use_case = use_case

    async def forecast(self, ticker: str) -> StockForecastSummary | None:
        try:
            view = await self._use_case.forecast(ForecastQuery(symbol=ticker))
        except MarketDataUnavailableError:
            return None
        r = view.risk
        risk = (
            StockRiskSummary(
                vol_state=r.vol_state, drawdown_risk=r.drawdown_risk, rv_percentile=r.rv_percentile,
                evidence=tuple(StockRiskEvidence(e.key, e.test_rate, e.base_rate) for e in r.evidence),
            )
            if r is not None
            else None
        )
        p = view.probability
        if p is None:
            return StockForecastSummary(signal_direction=view.signal_direction, risk=risk)
        return StockForecastSummary(
            signal_direction=view.signal_direction,
            ready=p.ready,
            up_rate=p.up_rate,
            baseline_up_rate=p.baseline_up_rate,
            sample_size=p.sample_size,
            hits=p.hits,
            ci_low=p.ci_low,
            ci_high=p.ci_high,
            risk=risk,
        )
