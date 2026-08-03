"""지정가 체결 판정 — 순수 함수(게임 시각은 인자로만 들어온다).

`liquidation.resolve_close`와 같은 구조다: 저장된 대기 주문을 두고, **조회가 도달한 시점에**
지나간 구간을 훑어 조건을 처음 만족한 틱을 찾는다(game-strategy §7-12). cron이 없으므로
"체결됐는지"는 언제나 이 함수가 사후에 답한다.

스캔 범위는 `placed_tick+1 ~ min(now, expires_tick)`이다. 만료가 없으면 장기 미접속자의
판정 비용이 폭발한다 — 만료는 UX 장치가 아니라 **성능 장치**다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# le: 지정가 **이하로 내려오면** 체결 (매수 예약·롱 손절·숏 익절)
# ge: 지정가 **이상으로 올라가면** 체결 (매도 예약·롱 익절·숏 손절)
TRIGGERS = ("le", "ge")


@dataclass(frozen=True)
class FillHit:
    """체결된 틱과 체결가."""

    tick: int
    price_krw: int


def resolve_fill(
    price_of: Callable[[int], int],
    *,
    trigger: str,
    limit_price_krw: int,
    placed_tick: int,
    now_tick: int,
    expires_tick: int,
) -> FillHit | None:
    """조건을 처음 만족한 틱. 아직이면 None.

    **체결가는 그 틱의 계산값이 아니라 지정가다.** 결정론 모델에는 갭이 없어서 "유리하게
    빗나간 가격"을 정의할 근거가 없고, 그걸 유저 몫으로 주면 지정가를 일부러 멀리 걸수록
    이득이 되는 구조가 된다(§7-12).
    """
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger는 {' 또는 '.join(TRIGGERS)}여야 합니다: {trigger}")

    for tick in range(placed_tick + 1, min(now_tick, expires_tick) + 1):
        price = price_of(tick)
        hit = price <= limit_price_krw if trigger == "le" else price >= limit_price_krw
        if hit:
            return FillHit(tick=tick, price_krw=limit_price_krw)
    return None


def is_expired(now_tick: int, expires_tick: int) -> bool:
    """만료 시각을 지났는가. 체결 판정보다 뒤에 본다 — 만료 틱의 체결은 유효하다."""
    return now_tick >= expires_tick
