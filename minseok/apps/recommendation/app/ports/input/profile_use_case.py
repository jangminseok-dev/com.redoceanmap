from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.profile_dto import ProfileDraft
from recommendation.domain.entities.profile_entity import InvestorProfile


class ProfileUseCase(ABC):
    """투자·창업 프로파일 유스케이스 — 저장(사용자당 1행 upsert)·내 것 조회·삭제."""

    @abstractmethod
    async def save(self, draft: ProfileDraft) -> InvestorProfile:
        """저장한다. 이미 있으면 덮어쓴다(설문 재작성은 갱신이지 오류가 아니다)."""
        ...

    @abstractmethod
    async def get_mine(self, user_id: int) -> InvestorProfile | None:
        """내 프로파일 — 미작성이면 None(오류 아님)."""
        ...

    @abstractmethod
    async def remove(self, user_id: int) -> bool:
        """삭제하고 실제로 지워졌는지 반환한다(없던 것 삭제는 False — 오류 아님)."""
        ...
