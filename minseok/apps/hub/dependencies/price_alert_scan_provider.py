from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.price_alert_scan_use_case import PriceAlertScanUseCase
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.price_alert_directory_port import PriceAlertDirectoryPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.app.use_cases.price_alert_scan_interactor import PriceAlertScanInteractor
from hub.dependencies.member_contact_provider import get_member_contact_port
from hub.dependencies.price_alert_directory_provider import get_price_alert_directory_port
from hub.dependencies.stock_status_provider import get_stock_status_port


def get_price_alert_scan_use_case(
    alerts: PriceAlertDirectoryPort = Depends(get_price_alert_directory_port),
    statuses: StockStatusPort = Depends(get_stock_status_port),
    contacts: MemberContactPort = Depends(get_member_contact_port),
) -> PriceAlertScanUseCase:
    return PriceAlertScanInteractor(alerts=alerts, statuses=statuses, contacts=contacts)
