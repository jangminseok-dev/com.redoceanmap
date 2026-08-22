"""종목 최신 상태 계약 DTO.

허브가 공개하는 앱 간 협력 계약. stock(스포크)이 동결 스냅샷(forecast_snapshots)과
최근 종가(price_bars)로 채워 반환하고, recommendation(스포크)이 관심 보드(③-M7)에 소비한다.
원시 수치만 담는다 — 문장화·배지 표기는 소비자 몫.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StockStatusInfo:
    ticker: str                    # 실제 저장 티커(예: 005930.KS) — 요청 심볼과 다를 수 있다
    as_of: datetime                # 신호 기준일(스냅샷)
    direction: str                 # UP | DOWN | NEUTRAL
    price: float                   # 최신 수집 종가 — 준실시간 아님
    change_pct: float | None       # 전일 대비(0.02 = +2%). 봉이 1개뿐이면 None
    up_rate: float | None          # 같은 신호 과거 상승 비율(표본 없으면 None)
    baseline_up_rate: float | None
    ready: bool                    # n≥100 + Wilson 하한 > 기준선(통계적 유의)
    price_as_of: datetime | None   # 가격 기준일 — 신호 기준일보다 최신일 수 있다
