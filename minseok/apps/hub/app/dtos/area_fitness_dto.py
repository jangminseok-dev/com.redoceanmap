"""입지 적합도 계약 DTO — market이 계산한 상권×업종 4축 판정을 소비자(chat)가 읽는 형태."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitnessComponentInfo:
    key: str
    label: str
    score: float   # 0.0 ~ 1.0
    weight: float


@dataclass(frozen=True)
class FitnessDiagnosisInfo:
    tone: str      # good | warn | bad
    message: str


@dataclass(frozen=True)
class AreaFitnessInfo:
    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    year_quarter: int
    total_score: float                       # 0.0 ~ 1.0
    components: tuple[FitnessComponentInfo, ...]
    diagnoses: tuple[FitnessDiagnosisInfo, ...]
    observed_ticket_price: int               # 객단가(원) = 매출액 ÷ 매출건수
    observed_similar_store_count: int
    has_sales: bool
    has_store: bool
