"""ProfileInteractor 테스트 — 스텁 리포지토리로 검증."""
from __future__ import annotations

import pytest

from recommendation.app.dtos.profile_dto import ProfileDraft
from recommendation.app.use_cases.profile_interactor import ProfileInteractor
from recommendation.domain.entities.profile_entity import InvestorProfile


class _StubProfiles:
    def __init__(self) -> None:
        self.by_user: dict[int, InvestorProfile] = {}

    async def upsert(self, profile: InvestorProfile) -> InvestorProfile:
        self.by_user[profile.user_id] = profile
        return profile

    async def find_by_user(self, user_id: int) -> InvestorProfile | None:
        return self.by_user.get(user_id)

    async def delete(self, user_id: int) -> bool:
        return self.by_user.pop(user_id, None) is not None


def _draft(**overrides) -> ProfileDraft:
    base = dict(
        user_id=7, purpose="startup", risk_level=2, budget_band="50m_100m",
        debt_burden="none", horizon="mid",
    )
    return ProfileDraft(**{**base, **overrides})


async def test_저장하면_영속되고_라벨이_도메인_매핑대로_나온다():
    repo = _StubProfiles()
    interactor = ProfileInteractor(profiles=repo)
    saved = await interactor.save(_draft())
    assert repo.by_user[7] is saved
    assert saved.purpose_label == "창업 준비"
    assert saved.risk_label == "안정추구형"
    assert saved.budget_label == "5천만~1억원"


async def test_재작성은_같은_사용자_행을_덮어쓴다():
    repo = _StubProfiles()
    interactor = ProfileInteractor(profiles=repo)
    await interactor.save(_draft(risk_level=2))
    updated = await interactor.save(_draft(risk_level=5, purpose="invest"))
    assert repo.by_user[7] is updated
    assert (updated.risk_level, updated.purpose) == (5, "invest")


async def test_어휘_밖_값은_ValueError로_거부한다():
    interactor = ProfileInteractor(profiles=_StubProfiles())
    with pytest.raises(ValueError):
        await interactor.save(_draft(budget_band="exact_73000000"))
    with pytest.raises(ValueError):
        await interactor.save(_draft(risk_level=6))


async def test_미작성_조회는_None이고_삭제는_멱등이다():
    repo = _StubProfiles()
    interactor = ProfileInteractor(profiles=repo)
    assert await interactor.get_mine(7) is None
    await interactor.save(_draft())
    assert await interactor.remove(7) is True
    assert await interactor.remove(7) is False
