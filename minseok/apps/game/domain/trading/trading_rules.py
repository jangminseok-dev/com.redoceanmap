"""매매 규칙 — 순수 계산 (game-strategy §3-2).

금액은 전부 **정수 원**이다. 부동소수를 누적하면 오차가 조용히 쌓이므로 각 계산의 끝에서
한 번만 반올림한다.

**레버리지는 없다(1배).** 숏도 증거금 100%다. 청산 로직을 두지 않는 이유는 오프라인 진행과
최악의 궁합이기 때문이다 — 미접속 중 청산되면 "게임오버 없음" 원칙과 충돌하고, 청산 시점을
결정론으로 확정하려면 경과 틱을 전량 순회해야 해서 O(log) 설계가 무너진다.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

INITIAL_CASH_KRW = 1_000_000

# 최소 생활자금 — 투자에 쓸 수 없게 **예약**한다.
#
# "손실이 하한 아래로 내려가면 깎아준다"가 아니라 "애초에 못 쓰게 한다"인 것이 중요하다.
# 전자는 게임이 돈을 만들어내 원장 불변식(§6-3)을 깨뜨린다. 후자는 손실 상한이 투입액이므로
# 잔고가 이 값 아래로 내려갈 수 없고, 원장은 현금 흐름과 정확히 일치한 채로 남는다.
RESERVED_CASH_KRW = 100_000

FEE_RATE = 0.0010  # 체결당 0.10% (왕복 0.2%)
# 무수수료면 최적 전략이 매 틱 스캘핑이 된다 — 우리가 없애려던 탭 노가다의 재발명이다.
#
# 0.15%에서 낮췄다(2026-07-31, σ 캘리브레이션 반영 시). 두 가지 근거가 겹친다.
# ① 한국 주식 실제 왕복은 온라인 위탁수수료 0.015%×2 + 증권거래세 0.18% ≈ 0.21%라
#    0.30%는 현실보다 비쌌다. 0.20%가 앵커에 더 가깝다.
# ② 캘리브레이션으로 σ 배열이 바뀌면서 무작위 전략의 수수료 부담이 밸런스 계약의
#    손실 비율 밴드를 넘겼다(55.2% > 55%). 근거는 game-strategy §3-4 표.

SHORT_CARRY_RATE_PER_GAME_DAY = 0.0002  # 숏 보유비용 0.02%/게임일


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class EntryCost:
    principal_krw: int  # 롱은 매수대금, 숏은 증거금
    fee_krw: int
    total_krw: int  # 지갑에서 실제로 빠지는 금액


@dataclass(frozen=True)
class CloseResult:
    proceeds_krw: int  # 지갑으로 돌아오는 금액 (하한 0)
    fee_krw: int
    carry_krw: int  # 숏 보유비용
    realized_pnl_krw: int  # 회수액 − 투입액(진입 수수료 포함)


def investable_cash(cash_krw: int) -> int:
    """투자에 쓸 수 있는 현금. 최소 생활자금은 항상 남는다."""
    return max(0, cash_krw - RESERVED_CASH_KRW)


def entry_cost(price_krw: int, quantity: int) -> EntryCost:
    """진입에 필요한 금액. 롱·숏 동일(숏은 증거금 100%)."""
    principal = price_krw * quantity
    fee = round(principal * FEE_RATE)
    return EntryCost(principal_krw=principal, fee_krw=fee, total_krw=principal + fee)


def max_quantity(cash_krw: int, price_krw: int) -> int:
    """이 가격에 살 수 있는 최대 수량. 수수료까지 포함해 맞춘다."""
    budget = investable_cash(cash_krw)
    if price_krw <= 0 or budget <= 0:
        return 0
    quantity = int(budget // (price_krw * (1 + FEE_RATE)))
    # 반올림 때문에 1주 초과할 수 있다 — 실제 비용으로 되짚어 깎는다
    while quantity > 0 and entry_cost(price_krw, quantity).total_krw > budget:
        quantity -= 1
    return quantity


def close_result(
    side: Side,
    entry_price_krw: int,
    exit_price_krw: int,
    quantity: int,
    holding_game_days: float,
    entry_fee_krw: int,
) -> CloseResult:
    """청산 정산.

    숏 손실은 증거금까지로 막힌다 — 무한손실이 없어야 지갑이 음수가 되지 않는다(불변식).
    """
    principal = entry_price_krw * quantity
    exit_fee = round(exit_price_krw * quantity * FEE_RATE)

    if side is Side.LONG:
        carry = 0
        proceeds = max(0, exit_price_krw * quantity - exit_fee)
    else:
        gross_pnl = (entry_price_krw - exit_price_krw) * quantity
        gross_pnl = max(gross_pnl, -principal)  # 손실 상한 = 증거금
        carry = round(principal * SHORT_CARRY_RATE_PER_GAME_DAY * max(0.0, holding_game_days))
        proceeds = max(0, principal + gross_pnl - exit_fee - carry)

    return CloseResult(
        proceeds_krw=proceeds,
        fee_krw=exit_fee,
        carry_krw=carry,
        realized_pnl_krw=proceeds - (principal + entry_fee_krw),
    )
