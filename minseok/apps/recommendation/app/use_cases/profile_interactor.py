from __future__ import annotations

import logging

from recommendation.app.dtos.profile_dto import ProfileDraft
from recommendation.app.ports.input.profile_use_case import ProfileUseCase
from recommendation.app.ports.output.profile_repository import ProfileRepositoryPort
from recommendation.domain.entities.profile_entity import InvestorProfile

logger = logging.getLogger(__name__)


class ProfileInteractor(ProfileUseCase):
    """프로파일 대장 — 도메인 검증(엔티티 생성) 후 영속에 위임한다."""

    def __init__(self, profiles: ProfileRepositoryPort) -> None:
        self._profiles = profiles

    async def save(self, draft: ProfileDraft) -> InvestorProfile:
        # 어휘 밖 값은 엔티티 생성 시 ValueError — 라우터가 422로 변환한다
        profile = InvestorProfile(
            user_id=draft.user_id,
            purpose=draft.purpose,
            risk_level=draft.risk_level,
            budget_band=draft.budget_band,
            debt_burden=draft.debt_burden,
            horizon=draft.horizon,
        )
        saved = await self._profiles.upsert(profile)
        logger.info("[profile] user=%d 프로파일 저장(%s·%s)", draft.user_id, saved.purpose, saved.risk_label)
        return saved

    async def get_mine(self, user_id: int) -> InvestorProfile | None:
        return await self._profiles.find_by_user(user_id)

    async def remove(self, user_id: int) -> bool:
        deleted = await self._profiles.delete(user_id)
        logger.info("[profile] user=%d 프로파일 삭제(%s)", user_id, deleted)
        return deleted
