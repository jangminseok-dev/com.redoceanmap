"""뉴스 이벤트 사후 수익률 연구 계약 DTO.

stock(구현)과 admin(소비)을 잇는다. 원시 수치만 담고 판정 문장은 만들지 않는다.

**excess가 본체다.** 절대 수익률은 표본 기간의 시장 방향을 그대로 반영하므로,
기준선(전체 평균)을 뺀 초과분으로 읽어야 "이 이벤트가 남들보다 나은가"에 답할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass
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
