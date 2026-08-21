from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.bookmark_dto import BookmarkDraft
from recommendation.domain.entities.bookmark_entity import Bookmark


class BookmarkUseCase(ABC):
    """북마크 유스케이스 — 등록(멱등)·내 목록·삭제."""

    @abstractmethod
    async def add(self, draft: BookmarkDraft) -> Bookmark:
        """등록한다. 이미 있으면 기존 것을 반환한다(토글 UI의 재등록이 오류가 아니게)."""
        ...

    @abstractmethod
    async def list_mine(self, user_id: int) -> list[Bookmark]:
        """내 북마크 전부 — 최신 등록순."""
        ...

    @abstractmethod
    async def remove(self, user_id: int, target_type: str, target_key: str) -> bool:
        """삭제하고 실제로 지워졌는지 반환한다(없던 것 삭제는 False — 오류 아님)."""
        ...
