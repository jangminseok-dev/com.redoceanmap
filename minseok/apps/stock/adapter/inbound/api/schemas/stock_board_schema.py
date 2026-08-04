from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BoardRowSchema(BaseModel):
    ticker: str
    name: str                       # 표시용 한글명 — 모르는 티커는 티커 그대로
    as_of: datetime                 # 스냅샷 기준일
    direction: str                  # UP | DOWN | NEUTRAL
    score: float                    # 가중 합산 종합 점수 (-1~1)
    price: float                    # 최신 수집 종가 — 준실시간 아님
    change_pct: float | None        # 전일 대비 (0.012 = +1.2%)
    up_rate: float | None           # 과거 같은 신호의 상승 비율
    baseline_up_rate: float | None  # 평소 상승률
    edge_pct: float | None          # up_rate − baseline
    ready: bool                     # n≥100 + Wilson 하한 > 기준선
    sparkline: list[float]          # 최근 종가(과거 → 최신)
    price_as_of: datetime | None    # 가격 기준일 — 신호 기준일(as_of)과 다를 수 있다
    volume: int | None              # 마지막 봉 거래량(주)
    turnover: float | None          # 거래대금 = 종가 × 거래량. 통화는 종목을 따른다(원/달러 혼재)


class StockBoardResponse(BaseModel):
    """GET /stock/board 응답 — 축적된 예측 스냅샷을 훑는 진입 화면용.

    매수 추천 순위가 아니라 신호가 뚜렷한 순서다. 확률은 과거 통계이며 미래를 보장하지 않는다.
    """

    horizon_days: int
    rows: list[BoardRowSchema]
