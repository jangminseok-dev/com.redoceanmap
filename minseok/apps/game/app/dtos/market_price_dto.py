from dataclasses import dataclass


@dataclass(frozen=True)
class MarketPriceQuery:

    ticks: int  # 반환할 최근 틱 개수


@dataclass(frozen=True)
class PricePoint:

    tick: int
    price_krw: int


@dataclass(frozen=True)
class SymbolPrices:

    symbol: str
    name: str
    sector: str
    price_krw: int
    change_pct: float       # 게임 1일 전 대비
    series: tuple[PricePoint, ...]


@dataclass(frozen=True)
class MarketEventView:
    """최근 호재·악재. 저장하지 않고 매번 재현한다 — 같은 틱이면 같은 목록이다."""

    tick: int
    scope: str  # symbol | sector | market
    target: str
    target_name: str
    positive: bool
    headline: str


@dataclass(frozen=True)
class MarketPricesResponse:
    """게임 시세 응답.

    `virtual`은 항상 True다 — 실시세가 아님을 모든 응답이 스스로 밝힌다(game-harness §2).
    """

    virtual: bool
    calibrated: bool        # False면 종목 파라미터가 캘리브레이션 전 잠정값이다
    epoch_id: int
    rule_version: str
    tick: int
    game_day: int
    game_quarter: int
    season_over: bool
    symbols: tuple[SymbolPrices, ...]
    events: tuple[MarketEventView, ...]
