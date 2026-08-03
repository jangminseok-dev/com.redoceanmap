"""지수 선물 DTO.

포지션은 주식과 같은 테이블을 쓴다(`instrument='FUTURES'`) — 선물도 증거금과 만기를 가진
포지션이라 새 저장소를 만들 이유가 없다. 여기 DTO는 화면 계약만 다룬다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesQuery:
    user_id: int
    ticks: int = 120  # 지수 곡선 길이


@dataclass(frozen=True)
class IndexPoint:
    tick: int
    point: int


@dataclass(frozen=True)
class FuturesPositionView:
    id: int
    contract_code: str
    side: str
    contracts: int
    entry_price_krw: int   # 1계약 진입 금액
    current_price_krw: int
    market_value_krw: int  # 지금 청산하면 돌아올 금액
    unrealized_pnl_krw: int
    unrealized_pct: float
    expires_tick: int
    ticks_to_expiry: int


@dataclass(frozen=True)
class FuturesView:
    """근월물 하나 + 현물 지수 + 내 선물 포지션."""

    virtual: bool
    contract_code: str
    expiry_tick: int
    ticks_to_expiry: int
    index_point: int              # 현물 지수
    futures_point: int            # 선물 가격
    basis_pct: float              # (선물 − 현물) ÷ 현물. 양수면 콘탱고
    contract_value_krw: int       # 1계약 명목
    margin_per_contract_krw: int  # 1계약 증거금
    multiplier_krw: int
    margin_ratio: float
    max_contracts: int            # 지금 잔고로 살 수 있는 계약 수
    series: tuple[IndexPoint, ...]
    positions: tuple[FuturesPositionView, ...]
    investable_krw: int
    # 게임 시각
    tick: int
    game_day: int
    game_quarter: int
    season_over: bool


@dataclass(frozen=True)
class OpenFuturesCommand:
    user_id: int
    side: str  # LONG | SHORT
    contracts: int


@dataclass(frozen=True)
class CloseFuturesCommand:
    user_id: int
    position_id: int


@dataclass(frozen=True)
class FuturesReceipt:
    position_id: int
    contract_code: str
    side: str
    contracts: int
    price_krw: int          # 1계약 체결 금액
    futures_point: int
    fee_krw: int
    margin_krw: int
    cash_delta_krw: int
    realized_pnl_krw: int | None
    cash_krw: int
    expires_tick: int
    tick: int
