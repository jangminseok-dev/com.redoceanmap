"""지수 선물 — 계약 시리즈·베이시스·만기 정산 (game-strategy §3-5).

현금정산 방식이다. 실물 인수도가 없고 만기에 지수값으로 차액만 주고받는다.

**청산 엔진을 쓰지 않는다.** 레버리지 주식은 만료 구간을 틱 단위로 훑어 청산 시점을 찾지만
(8ms/포지션), 지수는 한 번 평가에 0.58ms라 같은 스캔이 96ms가 되어 지갑 응답이 무너진다.
그런데 지수는 스캔할 필요가 없다 — 실측상 만기 구간(180틱) 변동은 표준편차 1.64%·최대 7.99%로
증거금 20%에 한참 못 미쳐, 만기 전에 증거금이 소진되는 경로가 사실상 없다. 손실 상한 클램프
(`close_result`)만으로 지갑이 음수가 되지 않는다.

⚠️ 이 가정은 테스트로 고정한다(`test_futures_contract.py`). 깨지면 청산 엔진이 필요해진다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market.market_events import MarketEvent
from game.domain.market.price_engine import index_at
from game.domain.rng.deterministic import normal

INDEX_CODE = "GXI"

# 만기 주기. 거래 가능 계약은 **근월물 하나**다 — 차월물(360틱)은 관측 변동이 증거금을
# 넘길 수 있고, 근월물만 두면 그 구간이 구조적으로 생기지 않는다.
FUTURES_EXPIRY_TICKS = 180  # 게임 3일 = 현실 3시간

CONTRACT_MULTIPLIER_KRW = 500  # 1계약 = 지수 1pt당 500원 → 명목 ≈ 50만원
FUTURES_MARGIN_RATIO = 0.20    # 증거금 20% = 5배. 실측 최대 변동 7.99%의 2.5배 여유
FUTURES_LEVERAGE = 5           # = round(1 / FUTURES_MARGIN_RATIO)

MIN_TICKS_TO_EXPIRY = 5  # 만기 직전 진입 금지 — "1틱짜리 계약"을 막는다(최종거래일 개념)

# 베이시스 — 선물가가 현물지수와 갈리는 폭.
_CARRY_PER_GAME_DAY = 0.0004  # 보유비용(콘탱고 방향)
_SPREAD_SCALE = 0.010         # 계약별 고유 편차 ±1.0%
_SPREAD_TAU_DAYS = 3.0        # 편차가 완전히 실리는 잔존일


@dataclass(frozen=True)
class FuturesContract:
    """근월물 하나."""

    code: str          # GXIF-01260 — 만기 틱을 코드에 박는다(저장할 것이 없다)
    expiry_tick: int
    multiplier_krw: int
    margin_ratio: float


def contract_code(expiry_tick: int) -> str:
    return f"GXIF-{expiry_tick:05d}"


def front_contract(tick: int) -> FuturesContract:
    """`tick` 시점에 거래되는 근월물. 만기가 지나면 다음 계약으로 자동으로 넘어간다."""
    step = max(0, tick) // FUTURES_EXPIRY_TICKS + 1
    expiry = min(step * FUTURES_EXPIRY_TICKS, SEASON_TICKS)
    return FuturesContract(
        code=contract_code(expiry),
        expiry_tick=expiry,
        multiplier_krw=CONTRACT_MULTIPLIER_KRW,
        margin_ratio=FUTURES_MARGIN_RATIO,
    )


def basis_ratio(expiry_tick: int, tick: int) -> float:
    """현물 대비 선물 프리미엄 비율. **만기에 정확히 0이다.**

    `exp(r·τ + s·τ/τ₀) − 1` 꼴이라 잔존 τ가 0으로 가면 자동으로 현물에 수렴한다 —
    만기 수렴이 별도 규칙이 아니라 수식의 성질이 된다. `s`는 계약마다 다른 고유 편차라
    어떤 계약은 콘탱고, 어떤 계약은 백워데이션이 된다(전량 콘탱고면 숏이 공짜 수익이 된다).
    """
    tau_days = max(0.0, (expiry_tick - tick) / TICKS_PER_GAME_DAY)
    if tau_days <= 0:
        return 0.0
    spread = normal("fut-basis", contract_code(expiry_tick)) * _SPREAD_SCALE
    exponent = _CARRY_PER_GAME_DAY * tau_days + spread * min(1.0, tau_days / _SPREAD_TAU_DAYS)
    return math.exp(exponent) - 1.0


def futures_price(
    expiry_tick: int, tick: int, extra_events: tuple[MarketEvent, ...] = ()
) -> int:
    """선물 가격(지수 포인트). 만기에는 정산가와 같다."""
    spot = index_at(min(tick, expiry_tick), extra_events)
    return max(1, round(spot * (1.0 + basis_ratio(expiry_tick, tick))))


def settlement_price(expiry_tick: int, extra_events: tuple[MarketEvent, ...] = ()) -> int:
    """만기 정산가 — 그 시점의 **현물 지수**다(선물가가 아니다)."""
    return index_at(expiry_tick, extra_events)


def contract_value_krw(index_point: int) -> int:
    """지수 포인트를 1계약 금액(원)으로."""
    return index_point * CONTRACT_MULTIPLIER_KRW
