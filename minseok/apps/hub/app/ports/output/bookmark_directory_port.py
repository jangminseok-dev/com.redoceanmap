from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.bookmark_directory_dto import BookmarkedArea, BookmarkedStock


class BookmarkDirectoryPort(ABC):
    """전체 북마크 열람 계약 — 허브 bookmark_alert(소비)와 recommendation(구현)을 잇는다.

    BookmarkBoard(사용자 1명의 보드)와 달리 **전 사용자 횡단** 조회다 — 알림 스캔이
    "찜한 사람이 있는 대상만" 상태를 확인하기 위한 축. 상권 북마크는 분기 단위라
    '신호 발생' 알림이 아니라 **신규 분기 반영·등급 변동** 알림 대상이다(B1, 2026-08-24 —
    v1의 "계약에 없다" 판정을 갱신).
    """

    @abstractmethod
    async def stock_bookmarks(self) -> list[BookmarkedStock]:
        """전 사용자의 종목 북마크 — 없으면 빈 리스트."""
        ...

    @abstractmethod
    async def area_bookmarks(self) -> list[BookmarkedArea]:
        """전 사용자의 상권 북마크 — 없으면 빈 리스트. 수신 거부 회원은 제외."""
        ...

    @abstractmethod
    async def telegram_chat_ids(self, user_ids: list[int]) -> dict[int, str]:
        """user_id → 텔레그램 chat_id(I-7). 미등록 회원은 키 자체가 없다.

        MemberContactPort의 이메일과 같은 위상(발송 목적 전용) — 채널 저장소가
        recommendation(user_alert_settings)이라 이 계약에 실린다."""
        ...
