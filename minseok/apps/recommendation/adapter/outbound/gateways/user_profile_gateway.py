from __future__ import annotations

from hub.app.dtos.user_profile_dto import UserProfileSummary
from hub.app.ports.output.user_profile_port import UserProfilePort
from recommendation.app.ports.input.profile_use_case import ProfileUseCase


class UserProfileGateway(UserProfilePort):
    """허브의 UserProfilePort를 recommendation(스포크)이 구현한다.

    스포크 → 허브 추상에만 의존(스타 토폴로지 허용). 도메인 엔티티를 허브 계약 DTO
    (문장 라벨)로 변환한다 — 라벨 매핑은 도메인(profile_entity)이 소유한다.
    """

    def __init__(self, use_case: ProfileUseCase) -> None:
        self._use_case = use_case

    async def get_profile(self, user_id: int) -> UserProfileSummary | None:
        profile = await self._use_case.get_mine(user_id)
        if profile is None:
            return None
        return UserProfileSummary(
            purpose=profile.purpose,
            purpose_label=profile.purpose_label,
            risk_label=profile.risk_label,
            budget_label=profile.budget_label,
            debt_label=profile.debt_label,
            horizon_label=profile.horizon_label,
        )
