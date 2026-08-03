import math

import pytest

from game.domain.market import market_events as events
from game.domain.market import price_engine, price_intervention as pi
from game.domain.market.symbol_params import SYMBOLS

SYMBOL = SYMBOLS[0]


def _intervention(**overrides) -> pi.PriceIntervention:
    base = dict(
        id=1,
        epoch_id=2,
        scope=pi.SCOPE_SYMBOL,
        target=SYMBOL.symbol,
        target_name=SYMBOL.name,
        from_tick=1_000,
        shock_pct=30.0,
        drift_pct_per_day=0.0,
        duration_days=2,
        headline="테스트 개입",
    )
    base.update(overrides)
    return pi.PriceIntervention(**base)


# --- 과거 불변 (이 기능의 존재 이유) ---------------------------------------

def test_개입_이전_틱의_가격은_바뀌지_않는다():
    """이게 깨지면 이미 체결된 체결가·분기 결산·차트가 통째로 소급 변조된다."""
    extra = pi.to_events((_intervention(from_tick=1_000),))
    for tick in (0, 500, 999):
        assert price_engine.price_at(SYMBOL, tick) == price_engine.price_at(
            SYMBOL, tick, None, extra
        )


def test_개입_이후_틱의_가격은_실제로_움직인다():
    extra = pi.to_events((_intervention(from_tick=1_000, shock_pct=30.0),))
    before = price_engine.price_at(SYMBOL, 1_010)
    after = price_engine.price_at(SYMBOL, 1_010, None, extra)
    assert after > before * 1.2  # 램프가 끝난 뒤라 30%가 거의 다 들어와 있다


def test_대상이_아닌_종목은_영향을_받지_않는다():
    extra = pi.to_events((_intervention(target=SYMBOL.symbol),))
    other = SYMBOLS[1]
    assert price_engine.price_at(other, 1_010) == price_engine.price_at(
        other, 1_010, None, extra
    )


def test_시장_전체_개입은_전_종목에_걸린다():
    extra = pi.to_events(
        (_intervention(scope=pi.SCOPE_MARKET, target="", target_name="시장 전체"),)
    )
    for params in SYMBOLS[:5]:
        assert price_engine.price_at(params, 1_010, None, extra) != price_engine.price_at(
            params, 1_010
        )


def test_창을_벗어나면_저절로_사라진다():
    """취소 기능이 없는 근거 — 개입은 이벤트 창 안에서 테이퍼로 소멸한다."""
    extra = pi.to_events((_intervention(from_tick=1_000),))
    far = 1_000 + events.EVENT_WINDOW_TICKS + 1
    assert price_engine.price_at(SYMBOL, far, None, extra) == price_engine.price_at(SYMBOL, far)


# --- 변환 -------------------------------------------------------------------

def test_목표가를_충격으로_역산한다():
    assert pi.shock_pct_for_target_price(100_000, 150_000) == pytest.approx(50.0)
    assert pi.shock_pct_for_target_price(100_000, 50_000) == pytest.approx(-50.0)


def test_목표가_개입은_그_가격_근처로_옮긴다():
    """일일 제한폭 안의 목표가는 그대로 닿는다."""
    tick = 2_000
    current = price_engine.price_at(SYMBOL, tick)
    target = round(current * 1.2)  # +20% — 상한가(+30%) 안쪽
    shock = pi.shock_pct_for_target_price(current, target)
    extra = pi.to_events((_intervention(from_tick=tick, shock_pct=shock),))
    moved = price_engine.price_at(SYMBOL, tick + events.EVENT_RAMP_TICKS, None, extra)
    # 램프 3틱 사이의 브라운 운동·테이퍼만큼은 어긋난다 — 방향과 크기가 맞으면 된다
    assert 0.9 < moved / target < 1.1


def test_상한가를_넘는_개입은_그날_상한가에서_멈춘다():
    """관리자가 목표가를 아무리 높게 잡아도 일일 제한폭을 뚫지 못한다.

    실제 시장과 같은 성질이고, 운영자가 실수로 10배를 넣어도 하루에 다 반영되지 않는다.
    """
    tick = 2_000
    day_open = price_engine._day_open(SYMBOL, (tick // 60) * 60, ())
    extra = pi.to_events((_intervention(from_tick=tick, shock_pct=200.0),))
    moved = price_engine.price_at(SYMBOL, tick + events.EVENT_RAMP_TICKS, None, extra)
    assert moved <= round(day_open * (1 + price_engine.DAILY_LIMIT_PCT))


def test_퍼센트가_로그_공간으로_옳게_넘어간다():
    event = pi.to_event(_intervention(shock_pct=30.0, drift_pct_per_day=5.0))
    assert event.shock == pytest.approx(math.log(1.30))
    assert event.drift_per_day == pytest.approx(math.log(1.05))
    assert event.positive is True
    assert pi.to_event(_intervention(shock_pct=-10.0)).positive is False


# --- 검증 -------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"shock_pct": 400.0},                       # 상한 초과
        {"drift_pct_per_day": 50.0},                # 상한 초과
        {"duration_days": 0},                       # 하한 미만
        {"duration_days": pi.MAX_DURATION_DAYS + 1},  # 창을 넘는 지속
        {"scope": "galaxy"},                        # 없는 범위
        {"shock_pct": 0.0, "drift_pct_per_day": 0.0},  # 아무 일도 안 하는 개입
    ],
)
def test_잘못된_개입은_거부한다(kwargs):
    base = dict(
        shock_pct=10.0, drift_pct_per_day=0.0, duration_days=2, scope=pi.SCOPE_SYMBOL
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        pi.validate(**base)


def test_지속_상한은_이벤트_창과_같다():
    """창 밖은 계산에서 빠지므로 6일을 받아도 5일에서 잘린다 — 화면이 거짓말하지 않게."""
    assert pi.MAX_DURATION_DAYS * 60 == events.EVENT_WINDOW_TICKS
