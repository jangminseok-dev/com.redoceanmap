"""입지 적합도 — "이상한 곳에 이상한 업종으로 창업하면 어떻게 되는가"의 핵심 (game-strategy §4-2).

순수 계산이다. 분포와 백분위는 market이 실데이터에서 뽑아 주고, **그 값으로 무엇을 판정할지가
게임 규칙**이다. 이 파일은 판정만 한다.

네 축을 쓴다.

1. 수요 정합 — 이 업종이 원래 팔리는 연령·성별과 이 상권을 지나는 사람의 연령·성별이 닮았는가
2. 시간대 정합 — 이 업종이 팔리는 시간대에 이 상권에 사람이 있는가
3. 포화도 — 같은 업종이 이미 얼마나 빽빽한가 (서울 백분위)
4. 생존 신호 — 이 조합이 실제로 얼마나 버티는가 (폐업률·영업개월 백분위)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 가중치 — 합 1.0. 계수 교체 지점(game-harness §5-3).
WEIGHT_DEMAND_MATCH = 0.35
WEIGHT_HOUR_MATCH = 0.30
WEIGHT_SATURATION = 0.20
WEIGHT_SURVIVAL = 0.15

# fitness = FLOOR + SPAN × 종합점수 → 0.4 ~ 1.6
FITNESS_FLOOR = 0.4
FITNESS_SPAN = 1.2


@dataclass(frozen=True)
class FitnessComponent:
    key: str  # demand_match | hour_match | saturation | survival
    label: str
    score: float  # 0.0 ~ 1.0
    weight: float


@dataclass(frozen=True)
class FitnessResult:
    fitness: float  # 0.4 ~ 1.6 — 매출 산식에 곱해지는 계수
    total_score: float  # 0.0 ~ 1.0 — 가중 합
    components: tuple[FitnessComponent, ...]


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """두 분포의 코사인 유사도. 한쪽이라도 비어 있으면 0.5(판단 보류)."""
    if len(a) != len(b):
        raise ValueError("분포 길이가 다르다")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.5  # 자료가 없는 것과 "안 맞는다"는 다르다
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def evaluate(
    *,
    industry_age_share: tuple[float, ...],
    industry_gender_share: tuple[float, ...],
    industry_hour_share: tuple[float, ...],
    floating_age_share: tuple[float, ...],
    floating_gender_share: tuple[float, ...],
    floating_hour_share: tuple[float, ...],
    saturation_percentile: float,
    closure_rate_percentile: float,
    operating_months_percentile: float,
) -> FitnessResult:
    """네 축을 재서 적합도 계수를 낸다."""
    # ① 수요 정합 — 연령이 성별보다 업종을 더 가른다(카페와 술집을 가르는 건 나이지 성별이 아니다)
    demand = 0.7 * cosine(industry_age_share, floating_age_share) + 0.3 * cosine(
        industry_gender_share, floating_gender_share
    )
    # ② 시간대 정합
    hour = cosine(industry_hour_share, floating_hour_share)
    # ③ 포화도 — 백분위가 높을수록 빽빽하다
    saturation = 1.0 - _clamp(saturation_percentile)
    # ④ 생존 신호 — 잘 닫는 곳은 감점, 오래 버티는 곳은 가점
    survival = 0.5 * (1.0 - _clamp(closure_rate_percentile)) + 0.5 * _clamp(
        operating_months_percentile
    )

    components = (
        FitnessComponent("demand_match", "수요 정합", round(demand, 4), WEIGHT_DEMAND_MATCH),
        FitnessComponent("hour_match", "시간대 정합", round(hour, 4), WEIGHT_HOUR_MATCH),
        FitnessComponent("saturation", "경쟁 여유", round(saturation, 4), WEIGHT_SATURATION),
        FitnessComponent("survival", "생존 신호", round(survival, 4), WEIGHT_SURVIVAL),
    )
    total = sum(c.score * c.weight for c in components)
    return FitnessResult(
        fitness=round(FITNESS_FLOOR + FITNESS_SPAN * total, 4),
        total_score=round(total, 4),
        components=components,
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
