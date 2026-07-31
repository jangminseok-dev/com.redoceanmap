import pytest

from game.domain.clock.game_epoch import GAME_DAYS_PER_QUARTER, QUARTERS_PER_SEASON
from game.domain.commerce.settlement import advise, pending_quarters, quarter_of


def test_분기_경계():
    assert quarter_of(0) == 1
    assert quarter_of(89) == 1
    assert quarter_of(90) == 2
    assert quarter_of(719) == QUARTERS_PER_SEASON


def _pending(opened=0, settled=None, today=0, closed=None):
    # 앵커 기본값은 창업일 직전 — 리포지토리가 창업 시 넣는 값과 같다
    settled = opened - 1 if settled is None else settled
    return pending_quarters(
        opened_game_day=opened, settled_through_day=settled, today=today, closed_game_day=closed
    )


def test_진행_중인_분기는_정산하지_않는다():
    assert _pending(opened=0, today=50) == ()
    assert _pending(opened=0, today=88) == ()


def test_분기가_끝나야_정산한다():
    windows = _pending(opened=0, today=89)
    assert len(windows) == 1
    assert (windows[0].game_quarter, windows[0].start_day, windows[0].end_day) == (1, 0, 89)
    assert windows[0].days == GAME_DAYS_PER_QUARTER


def test_밀린_분기를_한_번에_돌려준다():
    """며칠 접속하지 않아도 분기는 밀려 있다가 순서대로 확정된다."""
    windows = _pending(opened=0, today=300)
    assert [w.game_quarter for w in windows] == [1, 2, 3]
    assert [(w.start_day, w.end_day) for w in windows] == [(0, 89), (90, 179), (180, 269)]


def test_이미_정산된_분기는_다시_나오지_않는다():
    """멱등 — 지연 실행이라 조회가 잦다."""
    assert [w.game_quarter for w in _pending(opened=0, settled=179, today=300)] == [3]
    assert _pending(opened=0, settled=269, today=300) == ()


def test_분기_중간_창업이면_남은_날짜만_센다():
    windows = _pending(opened=45, today=100)
    assert len(windows) == 1
    assert (windows[0].start_day, windows[0].end_day, windows[0].days) == (45, 89, 45)


def test_앵커가_창업일_직전이면_첫날부터_센다():
    """리포지토리가 창업 시 `opened_game_day - 1`을 넣는다 — 0으로 두면
    '0일차까지 정산됨'과 구분되지 않아 첫날이 통째로 빠진다(실제로 한 번 겪었다)."""
    assert _pending(opened=0, settled=-1, today=89)[0].start_day == 0
    assert _pending(opened=45, settled=44, today=100)[0].start_day == 45


def test_폐업한_가게는_폐업일까지만_정산한다():
    assert _pending(opened=0, today=300, closed=100) == (
        _pending(opened=0, today=300, closed=100)[0],
    )
    windows = _pending(opened=0, today=300, closed=100)
    assert [w.game_quarter for w in windows] == [1]


def test_시즌을_넘어서는_분기는_만들지_않는다():
    windows = _pending(opened=0, today=10_000)
    assert len(windows) == QUARTERS_PER_SEASON
    assert windows[-1].game_quarter == QUARTERS_PER_SEASON


# --- 조언 -------------------------------------------------------------------

def test_반려율이_높으면_시설을_권한다():
    advices = advise(
        profit_krw=100_000, average_turned_away_ratio=0.35, performance_ratio=1.2, fitness=1.4
    )
    assert any("시설" in a.message for a in advices)


def test_적합도가_낮은_적자는_이전을_권한다():
    advices = advise(
        profit_krw=-500_000, average_turned_away_ratio=0.0, performance_ratio=0.5, fitness=0.7
    )
    assert advices[0].tone == "bad"
    assert "폐업" in advices[0].message or "옮기" in advices[0].message


def test_적합도가_괜찮은_적자는_버티기를_제시한다():
    advices = advise(
        profit_krw=-100_000, average_turned_away_ratio=0.0, performance_ratio=0.9, fitness=1.2
    )
    assert any("고정비" in a.message or "인지도" in a.message for a in advices)


def test_잘_팔면_규모_확대를_권한다():
    advices = advise(
        profit_krw=2_000_000, average_turned_away_ratio=0.02, performance_ratio=1.4, fitness=1.5
    )
    assert any("규모" in a.message for a in advices)


@pytest.mark.parametrize("profit", [-1_000_000, 0, 1_000_000])
def test_조언은_최대_세_줄이다(profit):
    advices = advise(
        profit_krw=profit, average_turned_away_ratio=0.3, performance_ratio=0.8, fitness=1.0
    )
    assert 1 <= len(advices) <= 3
