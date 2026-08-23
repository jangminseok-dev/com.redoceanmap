"""AlertSettingInteractor 테스트 — 기본 수신(행 부재=True)·토글·멱등을 고정한다."""
from __future__ import annotations

from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft
from recommendation.app.use_cases.alert_setting_interactor import AlertSettingInteractor


class _StubSettings:
    def __init__(self) -> None:
        self.by_user: dict[int, bool] = {}

    async def find_by_user(self, user_id: int) -> bool | None:
        return self.by_user.get(user_id)

    async def upsert(self, user_id: int, email_alerts: bool) -> None:
        self.by_user[user_id] = email_alerts


async def test_설정한_적_없으면_기본_수신이다():
    interactor = AlertSettingInteractor(settings=_StubSettings())
    assert await interactor.get_mine(7) is True


async def test_끄면_꺼지고_다시_켜면_켜진다():
    repo = _StubSettings()
    interactor = AlertSettingInteractor(settings=repo)
    assert await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False)) is False
    assert await interactor.get_mine(7) is False
    assert await interactor.save(AlertSettingDraft(user_id=7, email_alerts=True)) is True
    assert await interactor.get_mine(7) is True


async def test_같은_값_재저장은_멱등이다():
    repo = _StubSettings()
    interactor = AlertSettingInteractor(settings=repo)
    await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False))
    await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False))
    assert repo.by_user == {7: False}
