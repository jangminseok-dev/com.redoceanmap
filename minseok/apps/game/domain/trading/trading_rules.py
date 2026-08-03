"""매매 규칙 — 순수 계산 (game-strategy §3-2).

금액은 전부 **정수 원**이다. 부동소수를 누적하면 오차가 조용히 쌓이므로 각 계산의 끝에서
한 번만 반올림한다.

**레버리지는 1·2·3·4배다.** 1배가 기본이고 숏도 1배면 증거금 100%다.

10단계까지는 레버리지를 두지 않았다. 근거는 "미접속 중 청산되면 '게임오버 없음' 원칙과
충돌하고, 청산 시점을 결정론으로 확정하려면 경과 틱을 전량 순회해야 해서 O(log) 설계가
무너진다"였다. **18단계에서 이 판정을 뒤집었다** — 두 가지가 해결됐기 때문이다.

1. **스캔 범위를 만료로 묶는다.** 레버리지 포지션에만 만료(180틱)를 강제하면 청산 판정
   구간이 `[진입, min(현재, 만료)]`로 유한해진다. 실측 8ms/포지션이고 동시 5개가 상한이라
   지갑 응답 목표(200ms) 안에 든다. `price_at`의 O(log) 성질은 그대로다 — 순회하는 것은
   구간이지 에포크 전체가 아니다.
2. **청산은 판정일 뿐 게임오버가 아니다.** 1배 포지션은 청산되지 않고 지갑도 음수가 되지
   않는다(손실 상한 = 증거금). 미접속 중 터진 포지션은 복귀 시 결과로 보여준다.

**L=1은 도입 전과 비트 단위로 같아야 한다** — `margin = notional`, `borrowed = 0`이 되어
아래 통합 수식이 기존 식으로 환원되고, 청산가도 정의되지 않는다(`liquidation_price` → None).
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

# --- 레버리지 (18단계) --------------------------------------------------------
LEVERAGE_TIERS = (1, 2, 3, 4)  # 슬라이더가 아니라 버튼 4개 — 소수 배율은 반올림만 늘린다

# 유지증거금률(명목 대비). 자기자본이 이 아래로 내려가면 청산한다.
# 4배 기준 청산선은 진입가 대비 -16.7%다(단순 전액손실선 -25%보다 앞이라 여유가 있다).
MAINTENANCE_MARGIN_RATIO = 0.10

# 레버리지 포지션의 만료. 이게 청산 스캔 범위를 유한하게 만드는 유일한 장치다
# (게임 3일 = 현실 3시간, 실측 8ms/포지션). 12단계 지정가 주문이 정한 값과 같다.
LEVERAGED_EXPIRY_TICKS = 180

# 차입금 보유비용. 공짜면 어떤 상황에서도 4배가 우월전략이 된다.
LEVERAGE_CARRY_RATE_PER_GAME_DAY = 0.0002

# 강제청산 추가 수수료(명목 기준). 반대매매가 자발 청산보다 불리해야 회피 유인이 생긴다.
LIQUIDATION_FEE_RATE = 0.0020

# 동시 보유 가능한 레버리지 포지션 수. 지갑 조회마다 각각 스캔하므로 비용 상한이다
# (5 × 8ms = 40ms).
MAX_LEVERAGED_POSITIONS = 5

# --- 지정가 주문 (12단계) -----------------------------------------------------
# 대기 주문의 스캔 범위 상한. 레버리지 만료와 같은 값이고 이유도 같다 — 만료가 없으면
# 장기 미접속자의 체결 판정이 전 구간 순회가 된다. 만료 대신 **연장**을 제공한다.
LIMIT_ORDER_EXPIRY_TICKS = LEVERAGED_EXPIRY_TICKS

# 동시 대기 주문 수. 판정 비용이 주문 수에 비례하므로 상한이 필요하다(위 레버리지와 같은 근거).
MAX_PENDING_LIMIT_ORDERS = 20


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class EntryCost:
    principal_krw: int  # 증거금 — 명목 ÷ 배율. 1배면 명목 전액이다
    fee_krw: int
    total_krw: int  # 지갑에서 실제로 빠지는 금액


@dataclass(frozen=True)
class CloseResult:
    proceeds_krw: int  # 지갑으로 돌아오는 금액 (하한 0)
    fee_krw: int
    carry_krw: int  # 숏 보유비용
    realized_pnl_krw: int  # 회수액 − 투입액(진입 수수료 포함)
    dividend_krw: int = 0  # 보유 중 지나간 배당. 롱은 +, 숏은 −(빌린 주식의 배당을 물어낸다)


def investable_cash(cash_krw: int) -> int:
    """투자에 쓸 수 있는 현금. 최소 생활자금은 항상 남는다."""
    return max(0, cash_krw - RESERVED_CASH_KRW)


def entry_cost(price_krw: int, quantity: int, leverage: int = 1) -> EntryCost:
    """진입에 필요한 금액.

    **수수료는 명목(notional) 기준이다** — 증거금 기준으로 매기면 4배가 수수료를 1/4만 내는
    셈이 되어 레버리지가 거래비용까지 할인해 준다.
    """
    notional = price_krw * quantity
    margin = notional // leverage if leverage > 1 else notional
    fee = round(notional * FEE_RATE)
    return EntryCost(principal_krw=margin, fee_krw=fee, total_krw=margin + fee)


def max_quantity(cash_krw: int, price_krw: int, leverage: int = 1) -> int:
    """이 가격에 살 수 있는 최대 수량. 수수료까지 포함해 맞춘다."""
    budget = investable_cash(cash_krw)
    if price_krw <= 0 or budget <= 0:
        return 0
    quantity = int(budget // (price_krw * (1 / leverage + FEE_RATE)))
    # 반올림 때문에 1주 초과할 수 있다 — 실제 비용으로 되짚어 깎는다
    while quantity > 0 and entry_cost(price_krw, quantity, leverage).total_krw > budget:
        quantity -= 1
    return quantity


def liquidation_price(side: Side, entry_price_krw: int, leverage: int) -> int | None:
    """강제청산 가격. **1배는 청산되지 않는다**(None).

    자기자본(증거금 ± 평가손익)이 명목의 `MAINTENANCE_MARGIN_RATIO` 아래로 내려가는 지점이다.
        롱  P* = 진입가 × (1 − 1/L) ÷ (1 − m)
        숏  P* = 진입가 × (1 + 1/L) ÷ (1 + m)
    L=1이면 롱은 0이 되고 숏은 손실 상한 규칙이 먼저 걸리므로 둘 다 청산 대상이 아니다.
    """
    if leverage <= 1:
        return None
    m = MAINTENANCE_MARGIN_RATIO
    if side is Side.LONG:
        return max(1, round(entry_price_krw * (1 - 1 / leverage) / (1 - m)))
    return max(1, round(entry_price_krw * (1 + 1 / leverage) / (1 + m)))


def close_result(
    side: Side,
    entry_price_krw: int,
    exit_price_krw: int,
    quantity: int,
    holding_game_days: float,
    entry_fee_krw: int,
    leverage: int = 1,
    forced: bool = False,
    dividend_per_share_krw: int = 0,
) -> CloseResult:
    """청산 정산.

    손실은 **증거금까지**로 막힌다 — 무한손실이 없어야 지갑이 음수가 되지 않는다(불변식).
    L=1에서 이 식은 도입 전 롱·숏 계산과 정확히 같은 값을 낸다.
    """
    notional = entry_price_krw * quantity
    margin = notional // leverage if leverage > 1 else notional
    borrowed = notional - margin
    exit_fee = round(exit_price_krw * quantity * FEE_RATE)
    if forced:
        # 반대매매는 자발 청산보다 불리하다
        exit_fee += round(exit_price_krw * quantity * LIQUIDATION_FEE_RATE)

    days = max(0.0, holding_game_days)
    if side is Side.LONG:
        gross_pnl = (exit_price_krw - entry_price_krw) * quantity
        carry = round(borrowed * LEVERAGE_CARRY_RATE_PER_GAME_DAY * days)
    else:
        gross_pnl = (entry_price_krw - exit_price_krw) * quantity
        # 숏은 빌린 주식 자체에 비용이 붙는다(명목 기준) — 1배에도 있다.
        # 여기에 현금 차입분(borrowed)이 더해진다.
        carry = round(
            notional * SHORT_CARRY_RATE_PER_GAME_DAY * days
            + borrowed * LEVERAGE_CARRY_RATE_PER_GAME_DAY * days
        )
    gross_pnl = max(gross_pnl, -margin)  # 손실 상한 = 증거금
    # 보유 중 지나간 배당. **숏은 물어낸다** — 빌린 주식의 배당은 원주인 몫이라
    # 공매도자가 대신 지급한다(실제 시장의 배당락 조정과 같은 원리다).
    dividend = dividend_per_share_krw * quantity
    if side is not Side.LONG:
        dividend = -dividend
    proceeds = max(0, margin + gross_pnl + dividend - exit_fee - carry)

    return CloseResult(
        proceeds_krw=proceeds,
        fee_krw=exit_fee,
        carry_krw=carry,
        realized_pnl_krw=proceeds - (margin + entry_fee_krw),
        dividend_krw=dividend,
    )
