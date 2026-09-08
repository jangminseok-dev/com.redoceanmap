"""입지 적합도 — "이 상권에 이 업종을 열면 맞는 자리인가"를 실데이터 분포로 판정한다.

순수 계산이다(game 스포크에서 2026-09 이관 — 게임 매출 계수 `fitness`는 버렸다).
분포와 백분위는 리포지토리가 실데이터에서 뽑아 주고, 이 파일은 판정만 한다.

네 축을 쓴다.

1. 수요 정합 — 이 업종이 원래 팔리는 연령·성별과 이 상권을 지나는 사람의 연령·성별이 닮았는가
2. 시간대 정합 — 이 업종이 팔리는 시간대에 이 상권에 사람이 있는가
3. 포화도 — 같은 업종이 이미 얼마나 빽빽한가 (서울 백분위)
4. 생존 신호 — 이 조합이 실제로 얼마나 버티는가 (폐업률·영업개월 백분위)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 가중치 — 합 1.0.
WEIGHT_DEMAND_MATCH = 0.35
WEIGHT_HOUR_MATCH = 0.30
WEIGHT_SATURATION = 0.20
WEIGHT_SURVIVAL = 0.15


@dataclass(frozen=True)
class FitnessComponent:
    key: str  # demand_match | hour_match | saturation | survival
    label: str
    score: float  # 0.0 ~ 1.0
    weight: float


@dataclass(frozen=True)
class FitnessResult:
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
    has_store: bool,
) -> FitnessResult:
    """네 축을 재서 종합점수(0~1)를 낸다.

    `has_store=False`면 포화도·생존 백분위가 **자료 없음으로 전부 0**이 들어온다. 그대로 쓰면
    경쟁 여유가 만점(1.0)이 되어, 아무 기록도 없는 상권이 가장 좋은 자리로 올라온다.
    분포와 같은 규칙으로 **판단을 보류**한다(`cosine`의 0.5와 같은 처리).
    """
    # ① 수요 정합 — 연령이 성별보다 업종을 더 가른다(카페와 술집을 가르는 건 나이지 성별이 아니다)
    demand = 0.7 * cosine(industry_age_share, floating_age_share) + 0.3 * cosine(
        industry_gender_share, floating_gender_share
    )
    # ② 시간대 정합
    hour = cosine(industry_hour_share, floating_hour_share)
    # ③ 포화도 — 백분위가 높을수록 빽빽하다
    saturation = 1.0 - _clamp(saturation_percentile) if has_store else 0.5
    # ④ 생존 신호 — 잘 닫는 곳은 감점, 오래 버티는 곳은 가점
    survival = (
        0.5 * (1.0 - _clamp(closure_rate_percentile))
        + 0.5 * _clamp(operating_months_percentile)
        if has_store
        else 0.5
    )

    components = (
        FitnessComponent("demand_match", "수요 정합", round(demand, 4), WEIGHT_DEMAND_MATCH),
        FitnessComponent("hour_match", "시간대 정합", round(hour, 4), WEIGHT_HOUR_MATCH),
        FitnessComponent("saturation", "경쟁 여유", round(saturation, 4), WEIGHT_SATURATION),
        FitnessComponent("survival", "생존 신호", round(survival, 4), WEIGHT_SURVIVAL),
    )
    total = sum(c.score * c.weight for c in components)
    return FitnessResult(total_score=round(total, 4), components=components)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
