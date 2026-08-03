from __future__ import annotations

from auth.adapter.outbound.log_mobile_gatekeeper_record_adapter import (
    LogMobileGatekeeperRecordAdapter,
)
from auth.app.ports.input.mobile_gatekeeper_use_case import MobileGatekeeperUseCase
from auth.app.use_cases.mobile_gatekeeper_interactor import MobileGatekeeperInteractor


def get_mobile_gatekeeper_use_case() -> MobileGatekeeperUseCase:
    return MobileGatekeeperInteractor(record=LogMobileGatekeeperRecordAdapter())
