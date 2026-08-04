import pytest

from game.app.dtos.market_price_dto import MarketPriceQuery
from game.app.exceptions import InvalidTickRange, UnknownSymbol
from game.app.use_cases.market_price_interactor import (
    MAX_CANDLE_DAYS,
    MAX_TICKS,
    MIN_CANDLE_DAYS,
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


# --- 일봉·종목정보 (옵트인) ---------------------------------------------------

async def test_종목을_지정하지_않으면_봉을_계산하지_않는다():
    """전 종목 봉은 응답 목표를 넘긴다 — 기본은 계산하지 않는 것이다."""
    result = await MarketPriceInteractor(clock=_StubClock(12_345)).list_prices(
        MarketPriceQuery(ticks=30)
    )
    assert result.candles == ()
    assert result.symbol_info is None


async def test_지정한_종목의_봉과_카드가_함께_나온다():
    result = await MarketPriceInteractor(clock=_StubClock(12_345)).list_prices(
        MarketPriceQuery(ticks=30, candle_symbol="GX01", candle_days=7)
    )
    assert len(result.candles) == 7
    info = result.symbol_info
    assert info is not None
    assert info.symbol == "GX01"
    # 카드의 고저가는 그 봉들에서 나온 값이다 — 별도로 계산하지 않는다
    assert info.recent_high_krw == max(c.high_krw for c in result.candles)
    assert info.recent_low_krw == min(c.low_krw for c in result.candles)
    assert info.recent_days == len(result.candles)


async def test_없는_종목의_봉을_요청하면_거부한다():
    with pytest.raises(UnknownSymbol):
        await MarketPriceInteractor(clock=_StubClock(1_000)).list_prices(
            MarketPriceQuery(ticks=30, candle_symbol="ZZ99")
        )


@pytest.mark.parametrize("days", [MIN_CANDLE_DAYS - 1, 0, -3, MAX_CANDLE_DAYS + 1, 400])
async def test_허용_범위_밖의_candle_days는_거부한다(days):
    with pytest.raises(InvalidTickRange):
        await MarketPriceInteractor(clock=_StubClock(12_345)).list_prices(
            MarketPriceQuery(ticks=30, candle_symbol="GX01", candle_days=days)
        )


async def test_섹터_그룹이_전_종목에_노출된다():
    """화면의 섹터 필터가 쓰는 축 — 도메인에 이미 있던 값을 내보내기만 한다."""
    result = await MarketPriceInteractor(clock=_StubClock(3_000)).list_prices(
        MarketPriceQuery(ticks=10)
    )
    groups = {s.sector_group for s in result.symbols}
    assert groups == {s.sector_group for s in SYMBOLS}
    # 그룹마다 4종목이어야 섹터 이벤트가 §3-3의 "3~5종목"에 든다
    assert all(sum(1 for s in SYMBOLS if s.sector_group == g) == 4 for g in groups)


async def test_표의_거래량은_차트_마지막_봉과_같은_값이다():
    """표(symbols)와 차트(candles)가 같은 날 같은 종목에 다른 거래량을 보이면 안 된다.

    표는 봉을 만들지 않고 당일 시가 1회 평가로 `daily_volume`을 부르므로, 계산 경로가
    갈라지지 않았는지 여기서 못박는다.
    """
    result = await MarketPriceInteractor(clock=_StubClock(12_345)).list_prices(
        MarketPriceQuery(ticks=30, candle_symbol="GX01", candle_days=7)
    )

    row = next(s for s in result.symbols if s.symbol == "GX01")
    assert row.simulated_volume == result.candles[-1].simulated_volume


async def test_표의_시총은_종목정보_카드와_같은_값이다():
    """표와 상세 카드가 같은 종목에 다른 시총을 보이면 안 된다."""
    result = await MarketPriceInteractor(clock=_StubClock(12_345)).list_prices(
        MarketPriceQuery(ticks=30, candle_symbol="GX01", candle_days=7)
    )

    row = next(s for s in result.symbols if s.symbol == "GX01")
    assert row.assumed_market_cap_krw == result.symbol_info.assumed_market_cap_krw


async def test_거래량과_시총은_전_종목에_실린다():
    """표가 36종목을 거래대금·시총으로 줄 세우려면 종목마다 있어야 한다."""
    result = await MarketPriceInteractor(clock=_StubClock(3_000)).list_prices(
        MarketPriceQuery(ticks=10)
    )

    assert len(result.symbols) == len(SYMBOLS)
    assert all(s.simulated_volume > 0 for s in result.symbols)
    assert all(s.assumed_market_cap_krw > 0 for s in result.symbols)


async def test_시즌_종료_틱에서도_봉과_거래량이_일치한다():
    """describe()는 시즌 마지막 틱을 SEASON_TICKS-1로 자르고 daily_candles는 자르지 않는다 —
    game_day를 moment에서 가져오면 정확히 이 지점에서 하루가 어긋난다."""
    result = await MarketPriceInteractor(clock=_StubClock(SEASON_TICKS)).list_prices(
        MarketPriceQuery(ticks=10, candle_symbol="GX01", candle_days=3)
    )

    row = next(s for s in result.symbols if s.symbol == "GX01")
    assert row.simulated_volume == result.candles[-1].simulated_volume
