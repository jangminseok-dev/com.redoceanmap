from datetime import datetime, timedelta, timezone

import pytest

from game.domain.clock import game_epoch as clock


def test_시즌_길이는_현실_30일이다():
    assert clock.SEASON_TICKS == 43_200
    assert clock.SEASON_TICKS * clock.TICK_SECONDS / 86_400 == 30.0


def test_에포크_시각이_틱_0이다():
    assert clock.tick_at(clock.GAME_EPOCH_START_UTC) == 0


def test_실제_1시간이_게임_1일이다():
    one_hour_later = clock.GAME_EPOCH_START_UTC + timedelta(hours=1)
    assert clock.tick_at(one_hour_later) == clock.TICKS_PER_GAME_DAY
    assert clock.describe(clock.tick_at(one_hour_later)).game_day == 1


def test_에포크_이전_시각은_0으로_잘린다():
    assert clock.tick_at(clock.GAME_EPOCH_START_UTC - timedelta(days=100)) == 0


def test_naive_datetime은_거부한다():
    """로컬 시각을 UTC로 오인하면 게임 시각이 9시간 어긋난다."""
    with pytest.raises(ValueError):
        clock.tick_at(datetime(2026, 8, 1, 0, 0, 0))


@pytest.mark.parametrize(
    ("tick", "game_day", "quarter", "day_of_quarter", "over"),
    [
        (0, 0, 1, 1, False),
        (59, 0, 1, 1, False),          # 게임 1일차 마지막 틱
        (60, 1, 1, 2, False),
        (5_399, 89, 1, 90, False),     # 1분기 마지막 틱
        (5_400, 90, 2, 1, False),      # 2분기 첫 틱
        (43_199, 719, 8, 90, False),   # 시즌 마지막 틱
        (43_200, 719, 8, 90, True),    # 시즌 종료
        (99_999, 719, 8, 90, True),    # 한참 뒤에도 마지막 날에 고정
    ],
)
def test_게임_달력_경계(tick, game_day, quarter, day_of_quarter, over):
    result = clock.describe(tick)
    assert (result.game_day, result.game_quarter, result.day_of_quarter, result.season_over) == (
        game_day,
        quarter,
        day_of_quarter,
        over,
    )


def test_시즌_잔여_틱은_음수가_되지_않는다():
    assert clock.describe(clock.SEASON_TICKS + 5_000).ticks_remaining == 0
    assert clock.describe(0).ticks_remaining == clock.SEASON_TICKS


def test_에포크_시작은_KST_09시다():
    kst = timezone(timedelta(hours=9))
    assert clock.GAME_EPOCH_START_UTC.astimezone(kst).hour == 9
