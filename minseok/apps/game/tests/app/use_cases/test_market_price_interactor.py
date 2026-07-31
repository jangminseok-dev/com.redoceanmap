import pytest

from game.app.dtos.market_price_dto import MarketPriceQuery
from game.app.exceptions import InvalidTickRange
from game.app.use_cases.market_price_interactor import (
    MAX_TICKS,
    MIN_TICKS,
    MarketPriceInteractor,
)
from game.domain.clock.game_epoch import SEASON_TICKS
from game.domain.market.symbol_params import CALIBRATED_AT, SYMBOLS


class _StubClock:
    def __init__(self, tick: int):
        self._tick = tick

    def now_tick(self) -> int:
        return self._tick


async def test_전_종목의_현재가와_곡선을_낸다():
    result = await MarketPriceInteractor(clock=_StubClock(1_000)).list_prices(
        MarketPriceQuery(ticks=60)
    )

    assert len(result.symbols) == len(SYMBOLS)
    for symbol in result.symbols:
        assert len(symbol.series) == 60
        assert symbol.series[-1].tick == 1_000
        assert symbol.series[-1].price_krw == symbol.price_krw
        assert symbol.price_krw > 0


async def test_응답은_스스로_가상임을_밝힌다():
    """실시세로 오인되면 안 된다(game-harness §2)."""
    result = await MarketPriceInteractor(clock=_StubClock(500)).list_prices(
        MarketPriceQuery(ticks=10)
    )
    assert result.virtual is True
    # 캘리브레이션 여부는 상수 파일이 정하므로 그 상태를 그대로 따라간다 —
    # 값을 박아두면 σ를 다시 구울 때마다 무관한 테스트가 깨진다.
    assert result.calibrated is (CALIBRATED_AT is not None)


async def test_미래_틱은_만들지_않는다():
    """현재 틱보다 뒤의 점이 응답에 들어가면 §1-6 위반이다."""
    result = await MarketPriceInteractor(clock=_StubClock(30)).list_prices(
        MarketPriceQuery(ticks=240)
    )
    for symbol in result.symbols:
        assert max(p.tick for p in symbol.series) == 30


async def test_시즌_종료_후에는_마지막_틱에_멈춘다():
    result = await MarketPriceInteractor(
        clock=_StubClock(SEASON_TICKS + 10_000)
    ).list_prices(MarketPriceQuery(ticks=10))

    assert result.season_over is True
    for symbol in result.symbols:
        assert max(p.tick for p in symbol.series) == SEASON_TICKS


@pytest.mark.parametrize("ticks", [MIN_TICKS - 1, 0, -5, MAX_TICKS + 1, 10_000])
async def test_허용_범위_밖의_ticks는_거부한다(ticks):
    with pytest.raises(InvalidTickRange):
        await MarketPriceInteractor(clock=_StubClock(1_000)).list_prices(
            MarketPriceQuery(ticks=ticks)
        )


async def test_같은_틱을_두_번_물으면_같은_응답이다():
    interactor = MarketPriceInteractor(clock=_StubClock(2_222))
    first = await interactor.list_prices(MarketPriceQuery(ticks=30))
    second = await interactor.list_prices(MarketPriceQuery(ticks=30))
    assert first == second
