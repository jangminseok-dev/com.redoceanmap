"""데이터셋 적재 현황 계약 DTO.

어드민 데이터소스 화면이 소비한다. 데이터셋을 소유한 스포크가 채워서 반환한다 —
상권 5종은 market(`CommercialDataPort`), 주식 5종은 stock(`StockDatasetStatsPort`).
원시 사실만 담고 신선도 판정은 하지 않는다(판정은 소비자인 admin의 도메인 관심사).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetStat:
    """어드민 데이터소스 카드 1장 — 데이터셋별 적재 현황."""

    key: str
    name: str
    row_count: int
    latest_label: str | None  # 최신 분기(예: "20251") — 분기 단위 정적 데이터셋용
    # 최신 적재 시각. 신선도 판정의 유일한 원천이므로 반드시 '적재 시각'(created_at)이어야
    # 한다 — 기사 발행일이나 봉 시각을 쓰면 수집이 멈춰도 정상으로 보인다(2026-07-25 사고).
    latest_at: datetime | None = None
