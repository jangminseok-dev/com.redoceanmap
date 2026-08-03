from auth.app.dtos.mobile_gatekeeper_dto import MobileGatekeeperQuery
from auth.app.use_cases.mobile_gatekeeper_interactor import MobileGatekeeperInteractor


class _StubRecord:
    def __init__(self):
        self.records = []

    async def record(self, subject, note):
        self.records.append((subject, note))


async def test_자기소개는_실제_기능과_제약을_반환하고_기록을_남긴다():
    record = _StubRecord()
    result = await MobileGatekeeperInteractor(record=record).introduce_myself(
        MobileGatekeeperQuery(id=1, name="모바일 인증 (auth/mobile)")
    )
    assert result.id == 1
    assert "/auth/mobile/kakao" in result.introduction
    assert record.records[0][0] == "introduce_myself"
