from game.app.dtos.rulebook_dto import RulebookQuery
from game.app.use_cases.rulebook_interactor import RulebookInteractor
from game.domain.clock.game_epoch import SEASON_TICKS


class _StubRecord:
    def __init__(self):
        self.records = []

    async def record(self, subject, note):
        self.records.append((subject, note))


class _StubClock:
    def __init__(self, tick: int):
        self._tick = tick

    def now_tick(self) -> int:
        return self._tick


async def test_자기소개는_실기능을_서술하고_기록을_남긴다():
    record = _StubRecord()
    result = await RulebookInteractor(record=record, clock=_StubClock(0)).introduce_myself(
        RulebookQuery(id=12, name="게임 (game)")
    )
    assert result.id == 12
    assert result.name == "게임 (game)"
    assert record.records[0][0] == "introduce_myself"

    # 라우터 컨벤션 — 배역이 아니라 실기능·제약을 밝힌다
    assert "가상" in result.introduction
    assert "실제 매매를 실행하지 않" in result.introduction
    assert "가정치" in result.introduction


async def test_자기소개는_현재_게임_시각을_함께_낸다():
    """프론트가 첫 진입에 부르는 엔드포인트라 시각이 비면 안 된다(게이트 ②)."""
    result = await RulebookInteractor(
        record=_StubRecord(), clock=_StubClock(5_400)
    ).introduce_myself(RulebookQuery(id=12, name="게임 (game)"))

    assert result.tick == 5_400
    assert result.game_day == 90
    assert result.game_quarter == 2
    assert result.day_of_quarter == 1
    assert result.season_over is False
    assert result.ticks_remaining == SEASON_TICKS - 5_400


async def test_시즌이_끝나면_종료로_표시한다():
    result = await RulebookInteractor(
        record=_StubRecord(), clock=_StubClock(SEASON_TICKS + 100)
    ).introduce_myself(RulebookQuery(id=12, name="게임 (game)"))

    assert result.season_over is True
    assert result.ticks_remaining == 0
