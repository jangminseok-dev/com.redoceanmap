from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.bookmark_board_dto import BookmarkBoardItem


class BookmarkBoardUseCase(ABC):
    """관심 보드 유스케이스 — 내 북마크에 최신 상태(종목 신호·상권 점수)를 붙여 돌려준다."""

    @abstractmethod
    async def board(self, user_id: int) -> list[BookmarkBoardItem]:
        """내 북마크 전부 — 등록 최신순(③-M8 전까지 정렬 고정). 상태 조회 실패는 열화."""
        ...
