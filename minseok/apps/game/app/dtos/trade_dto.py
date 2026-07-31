from dataclasses import dataclass


@dataclass(frozen=True)
class OpenTradeCommand:

    user_id: int
    symbol: str
    side: str  # LONG | SHORT
    quantity: int


@dataclass(frozen=True)
class CloseTradeCommand:

    user_id: int
    position_id: int


@dataclass(frozen=True)
class TradeReceipt:
    """체결 결과. 체결가는 **요청이 도착한 틱**의 가격이다(지연 체결 없음)."""

    position_id: int
    symbol: str
    name: str
    side: str
    quantity: int
    price_krw: int
    fee_krw: int
    carry_krw: int  # 청산에만 붙는다(숏 보유비용)
    cash_delta_krw: int  # 지갑 증감 (진입은 음수)
    realized_pnl_krw: int | None  # 청산에만
    cash_krw: int  # 체결 후 잔고
    tick: int
