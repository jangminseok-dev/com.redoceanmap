"""AlertSettingInteractor 테스트 — 기본 수신(행 부재=True)·토글·텔레그램 등록을 고정한다."""
from __future__ import annotations

from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft
from recommendation.app.ports.output.alert_setting_repository import StoredAlertSetting
from recommendation.app.use_cases.alert_setting_interactor import AlertSettingInteractor


class _StubSettings:
    def __init__(self) -> None:
        self.by_user: dict[int, StoredAlertSetting] = {}

    async def find_by_user(self, user_id: int) -> StoredAlertSetting | None:
        return self.by_user.get(user_id)

    async def upsert(self, user_id: int, email_alerts: bool, telegram_chat_id) -> None:
        self.by_user[user_id] = StoredAlertSetting(
            email_alerts=email_alerts, telegram_chat_id=telegram_chat_id,
        )


async def test_설정한_적_없으면_기본_수신에_텔레그램_미등록이다():
    mine = await AlertSettingInteractor(settings=_StubSettings()).get_mine(7)
    assert mine.email_alerts is True and mine.telegram_chat_id is None


async def test_끄면_꺼지고_다시_켜면_켜진다():
    interactor = AlertSettingInteractor(settings=_StubSettings())
    off = await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False))
    assert off.email_alerts is False
    assert (await interactor.get_mine(7)).email_alerts is False
    on = await interactor.save(AlertSettingDraft(user_id=7, email_alerts=True))
    assert on.email_alerts is True


async def test_같은_값_재저장은_멱등이다():
    repo = _StubSettings()
    interactor = AlertSettingInteractor(settings=repo)
    await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False))
    await interactor.save(AlertSettingDraft(user_id=7, email_alerts=False))
    assert repo.by_user == {7: StoredAlertSetting(email_alerts=False, telegram_chat_id=None)}


async def test_텔레그램_chat_id를_등록하고_빈_값이면_해제한다():  # I-7
    repo = _StubSettings()
    interactor = AlertSettingInteractor(settings=repo)
    saved = await interactor.save(
        AlertSettingDraft(user_id=7, email_alerts=True, telegram_chat_id=" 123456 "))
    assert saved.telegram_chat_id == "123456"  # 공백 정리 후 저장
    cleared = await interactor.save(
        AlertSettingDraft(user_id=7, email_alerts=True, telegram_chat_id=""))
    assert cleared.telegram_chat_id is None    # 빈 문자열 = 해제
