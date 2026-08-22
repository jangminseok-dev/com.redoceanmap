from __future__ import annotations

import logging

from hub.app.dtos.commercial_data_dto import AreaScoreInfo
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from recommendation.app.dtos.bookmark_board_dto import BookmarkBoardItem
from recommendation.app.ports.input.bookmark_board_use_case import BookmarkBoardUseCase
from recommendation.app.ports.output.bookmark_repository import BookmarkRepositoryPort

logger = logging.getLogger(__name__)


class BookmarkBoardInteractor(BookmarkBoardUseCase):
    """관심 보드 대장 — 내 북마크를 축으로 종목 신호·상권 점수를 허브 포트로 붙인다.

    새 수집·새 테이블이 없다(③-M7) — 이미 있는 데이터의 조합만 한다. 상태 조회가 실패해도
    북마크 목록 자체는 항상 나간다(열화 동작 — 보드가 통째로 죽지 않는다).
    """

    def __init__(
        self,
        bookmarks: BookmarkRepositoryPort,
        stock_statuses: StockStatusPort,
        market: CommercialDataPort,
    ) -> None:
        self._bookmarks = bookmarks
        self._stock_statuses = stock_statuses
        self._market = market

    async def board(self, user_id: int) -> list[BookmarkBoardItem]:
        # 격리의 축 — 조회 범위가 처음부터 내 북마크뿐이라 남의 상태가 섞일 경로가 없다
        mine = await self._bookmarks.find_by_user(user_id)
        if not mine:
            return []

        stock_keys = [b.target_key for b in mine if b.target_type == "stock"]
        area_codes = [
            int(b.target_key) for b in mine
            if b.target_type == "area" and b.target_key.isdigit()
        ]
        statuses = await self._stock_statuses_or_empty(stock_keys)
        scores = await self._area_scores_or_empty(area_codes)

        items: list[BookmarkBoardItem] = []
        for b in mine:  # 리포지토리가 등록 최신순으로 준다 — M8 전까지 정렬 고정
            if b.target_type == "stock":
                items.append(BookmarkBoardItem(bookmark=b, stock=statuses.get(b.target_key)))
            else:
                code = int(b.target_key) if b.target_key.isdigit() else None
                items.append(BookmarkBoardItem(
                    bookmark=b, area=scores.get(code) if code is not None else None,
                ))
        return items

    async def _stock_statuses_or_empty(self, keys: list[str]) -> dict[str, StockStatusInfo]:
        if not keys:
            return {}
        try:
            return await self._stock_statuses.latest_statuses(keys)
        except Exception:
            logger.warning("[board] 종목 상태 조회 실패 — 상태 없이 열화", exc_info=True)
            return {}

    async def _area_scores_or_empty(self, codes: list[int]) -> dict[int, AreaScoreInfo]:
        if not codes:
            return {}
        try:
            return await self._market.get_area_scores(codes)
        except Exception:
            logger.warning("[board] 상권 점수 조회 실패 — 상태 없이 열화", exc_info=True)
            return {}
