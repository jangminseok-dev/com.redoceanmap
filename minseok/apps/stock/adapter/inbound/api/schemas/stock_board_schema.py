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
    rsi: float | None = None        # 신호 근거 — 역추세 신호라 "왜 떨어지는 종목에 상승 쪽 신호인가"를 설명한다
    bb_percent_b: float | None = None
    signal_days: int = 1            # 같은 방향 신호 연속 일수(오늘 포함)
    since_signal_pct: float | None = None  # 연속 신호 첫날 기준가 대비 최신가
    rv20: float | None = None              # 최근 20일 실현 변동성(연율)
    rv_percentile: float | None = None     # 자기 1년 분포 안 위치(0~1)
    vol_state: str | None = None           # HIGH | NORMAL | LOW — 향후 20거래일 변동성 확대 가능성
    trend: str | None = None               # UP | DOWN | MIXED(50·200일선)
    drawdown_risk: str | None = None       # HIGH | NORMAL | LOW — 20거래일 안 -10% 하락 가능성


class RiskStatSchema(BaseModel):
    key: str
    label: str
    outcome_label: str
    side: str
    test_rate: float | None
    base_rate: float | None
    lift: float | None
    n_eff: float
    train_lift: float | None
    validated: bool


class StockBoardResponse(BaseModel):
    """GET /stock/board 응답 — 축적된 예측 스냅샷을 훑는 진입 화면용.

    매수 추천 순위가 아니라 신호가 뚜렷한 순서다. 확률은 과거 통계이며 미래를 보장하지 않는다.
    """

    horizon_days: int
    rows: list[BoardRowSchema]
    risk_stats: list[RiskStatSchema] = []          # 위험 신호 상태별 검증 실측(최신 주간 리포트)
    risk_report_ran_at: datetime | None = None
    risk_test_period: str | None = None
