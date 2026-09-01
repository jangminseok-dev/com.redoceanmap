from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.news_alert_feed_port import NewsAlertFeedPort
from stock.adapter.outbound.gateways.news_alert_feed_gateway import NewsAlertFeedGateway


def get_news_alert_feed_gateway(db: AsyncSession = Depends(get_db)) -> NewsAlertFeedPort:
    """허브 NewsAlertFeedPort의 stock 구현 — main.py overrides가 주입."""
    return NewsAlertFeedGateway(session=db)
