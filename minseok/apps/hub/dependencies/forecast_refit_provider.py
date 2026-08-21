from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.forecast_refit_use_case import ForecastRefitIngestUseCase
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort
from hub.app.use_cases.forecast_refit_interactor import ForecastRefitInteractor


def get_forecast_refit_port() -> ForecastRefitPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(stock) 구현을 주입한다."""
    raise NotImplementedError(
        "get_forecast_refit_port는 main.py의 dependency_overrides로 stock 구현을 주입해야 합니다."
    )


def get_forecast_refit_use_case(
    refits: ForecastRefitPort = Depends(get_forecast_refit_port),
) -> ForecastRefitIngestUseCase:
    return ForecastRefitInteractor(refits=refits)
