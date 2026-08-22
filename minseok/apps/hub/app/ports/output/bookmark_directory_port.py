from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.bookmark_directory_dto import BookmarkedStock


class BookmarkDirectoryPort(ABC):
    """전체 종목 북마크 열람 계약 — 허브 bookmark_alert(소비)와 recommendation(구현)을 잇는다.

    BookmarkBoard(사용자 1명의 보드)와 달리 **전 사용자 횡단** 조회다 — 알림 스캔이
    "찜한 사람이 있는 종목만" 신호를 확인하기 위한 축. 상권 북마크는 계약에 없다
    (상권 점수는 분기 단위라 '신호 발생' 알림 대상이 아니다 — v1 범위 판정).
    """

    @abstractmethod
    async def stock_bookmarks(self) -> list[BookmarkedStock]:
        """전 사용자의 종목 북마크 — 없으면 빈 리스트."""
        ...
