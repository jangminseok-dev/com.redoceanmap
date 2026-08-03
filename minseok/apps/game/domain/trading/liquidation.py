"""레버리지 포지션의 마감 판정 — 강제청산과 만료 (game-strategy §7-18).

**지연 판정이다.** 서버가 매 틱 감시하지 않는다. 유저가 지갑을 조회할 때 "그동안 청산됐어야
했는가"를 되짚어 확정한다(8단계 분기 결산과 같은 패턴). 며칠 접속하지 않아도 결과는 같다.

이게 가능한 이유는 **만료가 스캔 범위를 묶기 때문**이다. 청산가를 처음 건드린 틱을 찾으려면
구간을 순회해야 하는데(가격이 구간 최저를 언제 찍었는지는 `price_at` 한 번으로 알 수 없다),
만료가 없으면 그 구간이 에포크 전체로 자란다. 만료 180틱이면 포지션당 `price_at` 180회
(≈8ms)로 상한이 잡힌다.

순수 계산이다 — 가격 함수를 주입받으므로 주식이든 지수든 같은 판정을 쓴다.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from game.domain.trading.trading_rules import Side, liquidation_price


@dataclass(frozen=True)
class CloseHit:
    """마감이 일어났어야 하는 시점."""

    tick: int
    price_krw: int
    reason: str  # liquidated | expired

    @property
    def forced(self) -> bool:
        """강제청산이면 추가 수수료가 붙는다. 만료는 정상 마감이라 붙지 않는다."""
        return self.reason == "liquidated"


def resolve_close(
    price_of: Callable[[int], int],
    *,
    side: Side,
    entry_price_krw: int,
    leverage: int,
    entry_tick: int,
    now_tick: int,
    expires_tick: int | None,
) -> CloseHit | None:
    """`now_tick`까지 마감됐어야 하면 그 시점을, 아니면 None을 돌려준다.

    같은 입력이면 언제 물어도 같은 답이다 — 가격이 결정론이라 청산 틱도 결정론이다.
    """
    if leverage <= 1 or expires_tick is None:
        return None  # 1배는 청산도 만료도 없다(도입 전과 같은 동작)

    trigger = liquidation_price(side, entry_price_krw, leverage)
    scan_end = min(now_tick, expires_tick)
    if trigger is not None:
        for tick in range(entry_tick + 1, scan_end + 1):
            price = price_of(tick)
            hit = price <= trigger if side is Side.LONG else price >= trigger
            if hit:
                # 이론 청산가가 아니라 **실제로 그 틱에 계산된 값**으로 정산한다.
                # 결정론이라 갭이 없고, 이론가보다 불리한 경우는 손실 상한이 받는다.
                return CloseHit(tick=tick, price_krw=price, reason="liquidated")

    if now_tick >= expires_tick:
        # 만료는 자동 마감이다 — 포기할 수 없는 포지션을 남기지 않는다(game-harness §2)
        return CloseHit(tick=expires_tick, price_krw=price_of(expires_tick), reason="expired")
    return None
