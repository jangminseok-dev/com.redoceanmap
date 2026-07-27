from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.news_event_study_port import NewsEventStudyPort
from stock.adapter.outbound.gateways.news_event_study_gateway import NewsEventStudyGateway


def get_news_event_study_gateway(db: AsyncSession = Depends(get_db)) -> NewsEventStudyPort:
    """허브 NewsEventStudyPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return NewsEventStudyGateway(session=db)
