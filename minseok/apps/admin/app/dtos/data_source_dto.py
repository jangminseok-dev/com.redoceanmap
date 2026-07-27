from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DataSourceCard:
    """어드민 데이터소스 카드 1장 — 허브가 준 적재 사실 + admin이 내린 신선도 판정."""

    key: str
    name: str
    row_count: int
    latest_label: str | None  # 최신 분기(예: "20251") — 분기 단위 정적 데이터셋용
    latest_at: datetime | None  # 최신 적재 시각
    freshness: str  # FreshnessState.value
    expected: str | None  # 기대 주기(사람이 읽는 문구). 주기 없는 데이터셋은 None
    age_seconds: int | None


@dataclass(frozen=True)
class DataSourceListResponse:
    datasets: list[DataSourceCard]
