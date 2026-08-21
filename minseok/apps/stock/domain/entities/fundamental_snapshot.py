from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# yf-hist: 연간 재무제표 소급 백필(backfill_fundamentals.py) — as_of가 과거(공시 추정일)인
# 행이라 "지금" 스냅샷(yfinance·dart 주간 수집)과 소스로 구분한다. 백테스트(E2) 전용 원료.
SOURCES = ("yfinance", "dart", "yf-hist")


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    """종목 1개의 펀더멘털 스냅샷. (ticker, as_of, source)가 자연 유니크 키.

    지표는 소스에 따라 비어 있을 수 있다(예: 한국 종목은 yfinance가 PER/PBR/EPS를 안 준다 —
    DART 재무제표로 보강). 가격 파생 지표(기술적)와 달리 기업 자체의 가치·체력을 담는 축이다.
    """

    ticker: str
    as_of: date
    source: str  # yfinance | dart | yf-hist
    per: float | None = None             # 주가수익비율
    pbr: float | None = None             # 주가순자산비율
    roe: float | None = None             # 자기자본이익률 (0.15 = 15%)
    debt_to_equity: float | None = None  # 부채비율 (벤더 관례상 % 단위 혼재 — 소스별 해석)
    fcf: float | None = None             # 잉여현금흐름 (통화 단위)
    market_cap: float | None = None      # 시가총액 (통화 단위)
    eps: float | None = None             # 주당순이익
    bps: float | None = None             # 주당순자산

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("FundamentalSnapshot은 ticker가 필수입니다.")
        if self.source not in SOURCES:
            raise ValueError(f"source는 {SOURCES} 중 하나여야 합니다: {self.source}")
