import pytest

from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS

PLAIN = next(s for s in SYMBOLS if not s.meme)
MEME = next(s for s in SYMBOLS if s.meme)


def test_거래량은_결정론이다():
    """저장하지 않는 값이라 같은 (종목, 날)이면 언제 물어도 같아야 한다."""
    assert len({price_engine.daily_volume(PLAIN, 12, 0.03) for _ in range(20)}) == 1


def test_변동이_클수록_거래량이_는다():
    """뉴스가 뜬 날 거래량이 터지는 것이 눈에 보여야 한다."""
    quiet = price_engine.daily_volume(PLAIN, 12, 0.001)
    wild = price_engine.daily_volume(PLAIN, 12, 0.20)
    assert wild > quiet * 2


def test_밈_종목이_더_많이_거래된다():
    plain = price_engine.daily_volume(PLAIN, 12, 0.02)
    meme = price_engine.daily_volume(MEME, 12, 0.02)
    # 기준가가 달라 주수는 그것에도 좌우된다 — 거래대금으로 견준다
    assert meme * MEME.base_price_krw > plain * PLAIN.base_price_krw


def test_거래량은_항상_양수다():
    for params in SYMBOLS:
        for day in (0, 1, 100, 719):
            assert price_engine.daily_volume(params, day, 0.0) >= 1


def test_봉에_거래량이_실린다():
    candles = price_engine.daily_candles(PLAIN, 30 * TICKS_PER_GAME_DAY, 5)
    assert len(candles) == 5
    assert all(c.simulated_volume >= 1 for c in candles)


def test_종가_경로는_봉의_종가와_일치한다():
    """이동평균을 싼 경로로 계산해도 봉과 같은 값이라야 선이 봉 위에 얹힌다."""
    end = 30 * TICKS_PER_GAME_DAY + 40
    candles = price_engine.daily_candles(PLAIN, end, 10)
    closes = price_engine.daily_closes(PLAIN, end, 10)
    assert [c.close_krw for c in candles] == closes
