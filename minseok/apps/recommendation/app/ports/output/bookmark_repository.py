from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.domain.entities.bookmark_entity import Bookmark


class BookmarkRepositoryPort(ABC):
    """북마크 영속 아웃바운드 포트."""

    @abstractmethod
    async def upsert(self, bookmark: Bookmark) -> Bookmark:
        """저장한다. (user_id, target_type, target_key) 중복이면 기존 행을 반환한다."""
        ...

    @abstractmethod
    async def find_by_user(self, user_id: int) -> list[Bookmark]:
        """사용자의 북마크 전부 — 최신 등록순."""
        ...

    @abstractmethod
    async def count_by_user(self, user_id: int) -> int:
        ...

    @abstractmethod
    async def delete(self, user_id: int, target_type: str, target_key: str) -> bool:
        ...
