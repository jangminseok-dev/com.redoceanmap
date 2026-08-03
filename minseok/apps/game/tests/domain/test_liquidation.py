"""레버리지 청산·만료 판정.

여기서 지키는 계약은 셋이다.
1. **1배는 도입 전과 같다** — 청산도 만료도 없다.
2. **청산 틱은 결정론이다** — 프로세스가 달라도, 몇 번을 물어도 같은 답이다.
3. **스캔 범위는 만료로 묶인다** — 이게 없으면 O(log) 설계가 무너진다.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import game
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS
from game.domain.trading.liquidation import resolve_close
from game.domain.trading.trading_rules import (
    LEVERAGED_EXPIRY_TICKS,
    MAINTENANCE_MARGIN_RATIO,
    Side,
    close_result,
    liquidation_price,
)

_APPS_DIR = str(Path(game.__file__).resolve().parent.parent)
_SAMPLE = SYMBOLS[0]


def _price_of(params=_SAMPLE):
    return lambda tick: price_engine.price_at(params, tick)


# --- 청산가 ------------------------------------------------------------------

@pytest.mark.parametrize("side", [Side.LONG, Side.SHORT])
def test_1배는_청산가가_없다(side):
    """도입 전과 같은 동작 — 1배는 손실 상한만 있고 강제청산은 없다."""
    assert liquidation_price(side, 100_000, 1) is None


def test_배율이_높을수록_청산가가_진입가에_가깝다():
    prices = [liquidation_price(Side.LONG, 100_000, lev) for lev in (2, 3, 4)]
    assert prices == sorted(prices)  # 2배 < 3배 < 4배 순으로 진입가에 붙는다
    assert all(p < 100_000 for p in prices)


def test_숏은_위쪽에_청산가가_생긴다():
    assert liquidation_price(Side.SHORT, 100_000, 4) > 100_000


def test_청산선에서_자기자본이_유지증거금과_같다():
    """청산가의 정의 그대로인지 — 수식을 바꿔도 의미가 유지되게 고정한다."""
    entry, quantity, leverage = 100_000, 10, 4
    trigger = liquidation_price(Side.LONG, entry, leverage)
    notional = entry * quantity
    margin = notional // leverage
    equity = margin + (trigger - entry) * quantity
    assert equity == pytest.approx(trigger * quantity * MAINTENANCE_MARGIN_RATIO, rel=0.01)


# --- 마감 판정 ---------------------------------------------------------------

def test_1배는_마감_판정_대상이_아니다():
    assert (
        resolve_close(
            _price_of(),
            side=Side.LONG,
            entry_price_krw=price_engine.price_at(_SAMPLE, 1_000),
            leverage=1,
            entry_tick=1_000,
            now_tick=1_000 + LEVERAGED_EXPIRY_TICKS * 5,
            expires_tick=None,
        )
        is None
    )


def test_만료에_도달하면_자동_마감된다():
    """포기할 수 없는 포지션을 남기지 않는다(game-harness §2)."""
    entry_tick = 1_000
    expires = entry_tick + LEVERAGED_EXPIRY_TICKS
    hit = resolve_close(
        _price_of(),
        side=Side.LONG,
        entry_price_krw=price_engine.price_at(_SAMPLE, entry_tick),
        leverage=2,  # 실측상 2배는 거의 청산되지 않아 만료 경로가 드러난다
        entry_tick=entry_tick,
        now_tick=expires + 500,
        expires_tick=expires,
    )
    assert hit is not None
    assert hit.tick <= expires  # 만료를 넘겨 마감되지 않는다
    assert hit.forced is (hit.reason == "liquidated")


def test_만료_전이고_청산도_아니면_열려_있다():
    entry_tick = 1_000
    assert (
        resolve_close(
            _price_of(),
            side=Side.LONG,
            entry_price_krw=price_engine.price_at(_SAMPLE, entry_tick),
            leverage=2,
            entry_tick=entry_tick,
            now_tick=entry_tick + 5,
            expires_tick=entry_tick + LEVERAGED_EXPIRY_TICKS,
        )
        is None
    )


def test_청산되면_그_가격이_청산선을_넘어_있다():
    """이론 청산가가 아니라 **실제 그 틱의 계산값**으로 정산한다."""
    found = 0
    for params in SYMBOLS:
        for entry_tick in range(600, 20_000, 613):
            entry = price_engine.price_at(params, entry_tick)
            hit = resolve_close(
                _price_of(params),
                side=Side.LONG,
                entry_price_krw=entry,
                leverage=4,
                entry_tick=entry_tick,
                now_tick=entry_tick + LEVERAGED_EXPIRY_TICKS,
                expires_tick=entry_tick + LEVERAGED_EXPIRY_TICKS,
            )
            if hit and hit.reason == "liquidated":
                assert hit.price_krw <= liquidation_price(Side.LONG, entry, 4)
                found += 1
    assert found > 0, "표본에서 청산이 한 번도 일어나지 않았다 — 판정이 죽었을 수 있다"


def test_같은_포지션은_몇_번을_물어도_같은_틱에_마감된다():
    entry_tick = 2_000
    entry = price_engine.price_at(_SAMPLE, entry_tick)
    answers = {
        resolve_close(
            _price_of(),
            side=Side.LONG,
            entry_price_krw=entry,
            leverage=4,
            entry_tick=entry_tick,
            now_tick=entry_tick + LEVERAGED_EXPIRY_TICKS,
            expires_tick=entry_tick + LEVERAGED_EXPIRY_TICKS,
        )
        for _ in range(30)
    }
    assert len(answers) == 1


def test_청산_틱은_프로세스가_달라도_같다():
    """PYTHONHASHSEED가 달라도 같은 답이어야 한다(harness §8-1)."""
    code = (
        "from game.domain.market import price_engine as pe;"
        "from game.domain.market.symbol_params import SYMBOLS;"
        "from game.domain.trading.liquidation import resolve_close;"
        "from game.domain.trading.trading_rules import Side;"
        "p=SYMBOLS[0];e=pe.price_at(p,2000);"
        "h=resolve_close(lambda t: pe.price_at(p,t), side=Side.LONG, entry_price_krw=e,"
        " leverage=4, entry_tick=2000, now_tick=2180, expires_tick=2180);"
        "print(h.tick if h else None, h.price_krw if h else None)"
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": _APPS_DIR, "PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        assert result.returncode == 0, result.stderr
        outs.add(result.stdout.strip())
    assert len(outs) == 1, outs


# --- 정산 ---------------------------------------------------------------------

def test_강제청산은_자발_청산보다_불리하다():
    """회피 유인이 없으면 청산을 방치하는 것이 최적이 된다."""
    voluntary = close_result(
        Side.LONG, 100_000, 84_000, 10, 1.0, entry_fee_krw=1_000, leverage=4, forced=False
    )
    forced = close_result(
        Side.LONG, 100_000, 84_000, 10, 1.0, entry_fee_krw=1_000, leverage=4, forced=True
    )
    assert forced.proceeds_krw < voluntary.proceeds_krw


def test_손실은_증거금까지다():
    """지갑이 음수가 되지 않으려면 여기서 막혀야 한다(원장 불변식)."""
    for leverage in (1, 2, 3, 4):
        result = close_result(
            Side.LONG, 100_000, 1, 10, 5.0, entry_fee_krw=1_000, leverage=leverage
        )
        assert result.proceeds_krw >= 0
        notional = 100_000 * 10
        margin = notional // leverage if leverage > 1 else notional
        assert result.realized_pnl_krw >= -(margin + 1_000)


def test_숏도_증거금까지만_잃는다():
    for leverage in (1, 2, 3, 4):
        result = close_result(
            Side.SHORT, 100_000, 10_000_000, 10, 5.0, entry_fee_krw=1_000, leverage=leverage
        )
        assert result.proceeds_krw >= 0


def test_레버리지는_보유비용이_붙는다():
    """공짜면 어떤 상황에서도 4배가 우월전략이 된다."""
    plain = close_result(Side.LONG, 100_000, 100_000, 10, 3.0, entry_fee_krw=0, leverage=1)
    levered = close_result(Side.LONG, 100_000, 100_000, 10, 3.0, entry_fee_krw=0, leverage=4)
    assert plain.carry_krw == 0
    assert levered.carry_krw > 0
