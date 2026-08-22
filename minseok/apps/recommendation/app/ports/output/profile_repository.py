from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.domain.entities.profile_entity import InvestorProfile


class ProfileRepositoryPort(ABC):
    """프로파일 영속 아웃바운드 포트 — 사용자당 1행."""

    @abstractmethod
    async def upsert(self, profile: InvestorProfile) -> InvestorProfile:
        """저장한다. user_id 중복이면 전 필드를 덮어쓴다(설문 재작성)."""
        ...

    @abstractmethod
    async def find_by_user(self, user_id: int) -> InvestorProfile | None:
        ...

    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        ...
