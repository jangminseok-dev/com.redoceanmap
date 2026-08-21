from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stock.domain.entities.analysis_config import AnalysisConfig


@dataclass(frozen=True)
class ActiveSignalConfig:
    """현재 활성 판정 조합 — forecast·스냅샷 캡처가 쓰는 (키, 파라미터) 쌍.

    key는 스냅샷 `signal_config` 스탬프이자 캐시 키의 일부다 — 승격으로 키가 바뀌면
    forecast 캐시가 자연 무효화되고 채점 이력이 조합별로 분리된다.
    """

    key: str
    config: AnalysisConfig


@dataclass(frozen=True)
class ConfigHistoryRow:
    """판정 조합 이력 1행 — 어드민 승격 이력 화면용."""

    key: str
    is_active: bool
    config: AnalysisConfig
    source: str                      # seed | refit
    created_at: datetime
    activated_at: datetime | None
