from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from recommendation.adapter.outbound.gateways.alert_delivery_gateway import AlertDeliveryGateway
from recommendation.adapter.outbound.gateways.bookmark_directory_gateway import (
    BookmarkDirectoryGateway,
)
from recommendation.adapter.outbound.pg.bookmark_pg_repository import BookmarkPgRepository
from recommendation.app.ports.input.bookmark_use_case import BookmarkUseCase
from recommendation.app.use_cases.bookmark_interactor import BookmarkInteractor


def get_bookmark_use_case(db: AsyncSession = Depends(get_db)) -> BookmarkUseCase:
    return BookmarkInteractor(bookmarks=BookmarkPgRepository(session=db))


def get_bookmark_directory_gateway(db: AsyncSession = Depends(get_db)) -> BookmarkDirectoryPort:
    """허브 BookmarkDirectoryPort의 recommendation 구현. main.py가 주입한다."""
    return BookmarkDirectoryGateway(session=db)


def get_alert_delivery_gateway(db: AsyncSession = Depends(get_db)) -> AlertDeliveryPort:
    """허브 AlertDeliveryPort의 recommendation 구현(발송 상태 dedupe). main.py가 주입한다."""
    return AlertDeliveryGateway(session=db)
