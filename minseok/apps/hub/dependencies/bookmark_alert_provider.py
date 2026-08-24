from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.bookmark_alert_use_case import BookmarkAlertUseCase
from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.app.use_cases.bookmark_alert_interactor import BookmarkAlertInteractor
from hub.dependencies.alert_delivery_provider import get_alert_delivery_port
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.bookmark_directory_provider import get_bookmark_directory_port
from hub.dependencies.member_contact_provider import get_member_contact_port
from hub.dependencies.stock_status_provider import get_stock_status_port


def get_bookmark_alert_use_case(
    bookmarks: BookmarkDirectoryPort = Depends(get_bookmark_directory_port),
    statuses: StockStatusPort = Depends(get_stock_status_port),
    contacts: MemberContactPort = Depends(get_member_contact_port),
    deliveries: AlertDeliveryPort = Depends(get_alert_delivery_port),
    market: CommercialDataPort = Depends(get_commercial_data_port),
) -> BookmarkAlertUseCase:
    return BookmarkAlertInteractor(
        bookmarks=bookmarks, statuses=statuses, contacts=contacts, deliveries=deliveries,
        market=market,
    )
