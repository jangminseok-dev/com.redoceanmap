from dataclasses import dataclass


@dataclass(frozen=True)
class WalletQuery:

    user_id: int


@dataclass(frozen=True)
class PositionView:
    """미청산 포지션 1건 + 현재 시세 기준 평가."""

    id: int
    symbol: str
    name: str
    sector: str
    side: str
    quantity: int
    entry_tick: int
    entry_price_krw: int
    current_price_krw: int
    market_value_krw: int  # 지금 청산하면 돌아올 금액(수수료·보유비용 반영)
    unrealized_pnl_krw: int
    unrealized_pct: float


@dataclass(frozen=True)
class WalletView:

    cash_krw: int
    investable_krw: int  # 최소 생활자금을 뺀 실제 투자 가능액
    reserved_krw: int
    position_value_krw: int
    total_asset_krw: int  # 현금 + 포지션 평가
    initial_cash_krw: int
    total_return_pct: float
    # 게임 시각
    epoch_id: int
    rule_version: str
    tick: int
    game_day: int
    game_quarter: int
    season_over: bool
    positions: tuple[PositionView, ...]
