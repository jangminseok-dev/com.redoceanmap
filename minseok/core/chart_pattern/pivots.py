"""지그재그 피벗 추출 — 차트 패턴 탐지의 공통 전처리.

패턴(헤드앤숄더·더블탑·트랩)은 전부 **극값의 순서와 높이 관계**로 정의된다. 그래서
원계열을 그대로 매칭하지 않고 먼저 의미 있는 고점·저점만 남긴다. 임계(`min_swing_pct`)보다
작은 흔들림은 잡음으로 버린다 — 이 값이 작으면 노이즈가 전부 피벗이 되고, 크면 패턴이
사라진다.

외부 의존이 없는 순수 계산이다. 난수를 쓰지 않으므로 같은 입력은 항상 같은 피벗을 준다
(게임 쪽에서 결정론 게이트가 이 성질을 요구한다).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pivot:
    """극값 하나. `index`는 입력 계열의 위치다."""

    index: int
    price: float
    is_high: bool
    confirmed: bool  # False면 아직 반대 방향 스윙이 나오지 않은 진행 중 극값


def find_pivots(values: list[float], min_swing_pct: float) -> tuple[Pivot, ...]:
    """지그재그 피벗. 고점·저점이 번갈아 나온다.

    마지막 극값은 **미확정**(`confirmed=False`)으로 함께 돌려준다 — 트랩 패턴은
    "방금 뚫고 되돌아오는 중"을 봐야 해서 확정된 극값만으로는 잡히지 않는다.
    """
    if len(values) < 3 or min_swing_pct <= 0:
        return ()

    pivots: list[Pivot] = []
    high_index, high_value = 0, values[0]
    low_index, low_value = 0, values[0]
    direction = 0  # +1 상승 스윙 / -1 하락 스윙 / 0 미정

    def _pct(value: float, base: float) -> float:
        return 0.0 if base == 0 else (value - base) / abs(base) * 100.0

    for i in range(1, len(values)):
        value = values[i]

        if direction > 0:
            # 상승 스윙 — 고점을 밀어 올리다가 임계만큼 꺾이면 그 고점이 확정된다
            if value > high_value:
                high_index, high_value = i, value
            elif _pct(value, high_value) <= -min_swing_pct:
                pivots.append(Pivot(high_index, high_value, True, True))
                direction = -1
                low_index, low_value = i, value
        elif direction < 0:
            if value < low_value:
                low_index, low_value = i, value
            elif _pct(value, low_value) >= min_swing_pct:
                pivots.append(Pivot(low_index, low_value, False, True))
                direction = 1
                high_index, high_value = i, value
        else:
            # 방향 미정 — 최고·최저를 **동시에** 추적한다. 하나만 들면 기준점이 가격을
            # 따라 흘러내려 스윙이 영원히 임계를 넘지 못한다.
            if value > high_value:
                high_index, high_value = i, value
            if value < low_value:
                low_index, low_value = i, value
            if _pct(value, low_value) >= min_swing_pct:
                pivots.append(Pivot(low_index, low_value, False, True))
                direction = 1
                high_index, high_value = i, value
            elif _pct(value, high_value) <= -min_swing_pct:
                pivots.append(Pivot(high_index, high_value, True, True))
                direction = -1
                low_index, low_value = i, value

    # 진행 중인 극값. 방향이 아직 없으면(전 구간 단조) 마지막 점의 성격을 추세로 정한다
    if direction > 0:
        pivots.append(Pivot(high_index, high_value, True, False))
    elif direction < 0:
        pivots.append(Pivot(low_index, low_value, False, False))
    elif values[-1] >= values[0]:
        pivots.append(Pivot(high_index, high_value, True, False))
    else:
        pivots.append(Pivot(low_index, low_value, False, False))
    return tuple(pivots)


def average_swing_pct(values: list[float]) -> float:
    """인접 변화율의 평균(%). `min_swing_pct`의 기본값을 데이터에서 정할 때 쓴다.

    변동성이 종목마다 4배 넘게 차이나므로(게임 σ 2~9%/일) 고정 임계를 쓰면 어떤 종목은
    피벗이 0개, 어떤 종목은 전부 피벗이 된다.
    """
    if len(values) < 2:
        return 0.0
    steps = [
        abs(b - a) / abs(a) * 100.0
        for a, b in zip(values, values[1:])
        if a != 0
    ]
    return sum(steps) / len(steps) if steps else 0.0
