"""AI 모의투자 자동화 계약 DTO — cron이 step을 부르고, chat이 최근 판단을 읽는다."""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class PaperStepOutcome:
    as_of: datetime
    skipped: str | None
    filled: int
    decisions: int
    scored: int
    equity_rows: int


@dataclass(frozen=True)
class PaperOrderInfo:
    ticker: str
    action: str
    reason: str
    news_ids: list[int]


@dataclass(frozen=True)
class PaperDecisionInfo:
    """계정 1개의 최근 판단 1건 — chat이 '오늘 뭐 샀어' 답변에 쓴다(기록 보고 문형만)."""

    account: str  # exaone | signal
    as_of: date
    market_view: str
    orders: list[PaperOrderInfo]
    filled_tickers: list[str]
    equity_krw: float | None
    return_pct: float | None
