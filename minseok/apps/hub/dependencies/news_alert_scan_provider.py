from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.news_alert_scan_use_case import NewsAlertScanUseCase
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.news_alert_feed_port import NewsAlertFeedPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.app.use_cases.news_alert_scan_interactor import NewsAlertScanInteractor
from hub.dependencies.bookmark_directory_provider import get_bookmark_directory_port
from hub.dependencies.member_contact_provider import get_member_contact_port
from hub.dependencies.news_alert_feed_provider import get_news_alert_feed_port
from hub.dependencies.stock_status_provider import get_stock_status_port


def get_news_alert_scan_use_case(
    feed: NewsAlertFeedPort = Depends(get_news_alert_feed_port),
    bookmarks: BookmarkDirectoryPort = Depends(get_bookmark_directory_port),
    statuses: StockStatusPort = Depends(get_stock_status_port),
    contacts: MemberContactPort = Depends(get_member_contact_port),
) -> NewsAlertScanUseCase:
    return NewsAlertScanInteractor(
        feed=feed, bookmarks=bookmarks, statuses=statuses, contacts=contacts,
    )
