from __future__ import annotations

from dataclasses import dataclass

from hub.app.dtos.commercial_data_dto import AreaScoreInfo
from hub.app.dtos.stock_status_dto import StockStatusInfo
from recommendation.domain.entities.bookmark_entity import Bookmark


@dataclass(frozen=True)
class BookmarkBoardItem:
    """보드 한 줄 — 북마크에 '지금'을 붙인 것.

    상태(stock/area)는 대상 종류에 맞는 쪽 하나만 채워지고, 조회 실패·데이터 없음이면
    둘 다 None이다(열화 — 북마크 자체는 항상 내보낸다).
    """

    bookmark: Bookmark
    stock: StockStatusInfo | None = None
    area: AreaScoreInfo | None = None
