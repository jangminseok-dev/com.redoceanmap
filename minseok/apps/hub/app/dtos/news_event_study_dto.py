"""뉴스 이벤트 사후 수익률 연구 계약 DTO.

stock(구현)과 admin(소비)을 잇는다. 원시 수치만 담고 판정 문장은 만들지 않는다.

**excess가 본체다.** 절대 수익률은 표본 기간의 시장 방향을 그대로 반영하므로,
기준선(전체 평균)을 뺀 초과분으로 읽어야 "이 이벤트가 남들보다 나은가"에 답할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EventBucketRow:
    key: str               # 이벤트 유형 또는 감성대
    n: int
    avg_return_pct: float
    excess_pct: float      # 기준선 대비 — 이 값으로 읽는다
    positive_rate: float
    reliable: bool         # 표본 100건 이상


@dataclass(frozen=True)
class ShortHorizonRow:
    """분 단위 지평 — 5분봉으로 잰 발행 직후 반응(E1).

    일간과 판정 규칙은 같고 지평 단위만 다르다. `coverage_note`는 5분봉 보유 구간이라
    표본 수를 일간과 직접 비교하면 안 되는 이유를 담는다.
    """

    horizon_minutes: int
    total: int
    baseline_pct: float
    top_week_share: float
    warnings: list[str]
    coverage_note: str
    by_event: list[EventBucketRow]
    by_sentiment: list[EventBucketRow]


@dataclass(frozen=True)
class NewsEventStudyInfo:
    """최신 실행 1건."""

    ran_at: datetime
    params: dict
    horizon_days: int
    total: int
    baseline_pct: float
    top_week_share: float          # 가장 많이 몰린 주의 비중 — 표본 독립성 지표
    warnings: list[str]
    by_event: list[EventBucketRow]
    by_sentiment: list[EventBucketRow]
    # 구버전 리포트에는 없다 — 기본값 없이 두면 과거 행 매핑이 깨진다
    short_horizon: list[ShortHorizonRow] = field(default_factory=list)
