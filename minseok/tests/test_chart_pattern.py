"""차트 패턴 탐지 회귀 — 합성 계열로 8종을 각각 탐지·비탐지 검증한다.

실데이터로 검증하지 않는 이유: "이 구간이 헤드앤숄더인가"는 사람마다 갈리는 판정이라
회귀 테스트의 기준이 될 수 없다. 형태를 직접 만들어 넣고 그것을 찾는지만 본다.
"""
from __future__ import annotations

from core.chart_pattern import detect, find_pivots
from core.chart_pattern.pivots import average_swing_pct


def _ramp(start: float, end: float, steps: int) -> list[float]:
    """두 값을 잇는 직선 구간(끝점 제외) — 합성 계열의 조각."""
    return [start + (end - start) * i / steps for i in range(steps)]


def _series(*levels: float, steps: int = 6) -> list[float]:
    """꼭짓점 값들을 순서대로 잇는 지그재그 계열."""
    out: list[float] = []
    for a, b in zip(levels, levels[1:]):
        out.extend(_ramp(a, b, steps))
    out.append(levels[-1])
    return out


def _names(series: list[float]) -> set[str]:
    return {p.name for p in detect(series)}


# --- 피벗 -------------------------------------------------------------------

def test_피벗은_고점과_저점이_번갈아_나온다():
    pivots = find_pivots(_series(100, 120, 105, 130, 110), min_swing_pct=3)
    kinds = [p.is_high for p in pivots]
    assert all(a != b for a, b in zip(kinds, kinds[1:])), kinds


def test_임계보다_작은_흔들림은_피벗이_아니다():
    """잡음이 전부 피벗이 되면 어떤 형태든 매칭된다."""
    noisy = [100, 100.2, 99.9, 100.1, 100.0, 100.3, 99.8] * 3
    assert len(find_pivots(noisy, min_swing_pct=5)) == 1  # 진행 중 극값 하나뿐


def test_마지막_극값은_미확정으로_표시된다():
    """트랩 판정은 '방금 뚫고 되돌아오는 중'을 봐야 해서 확정 극값만으로는 부족하다."""
    pivots = find_pivots(_series(100, 120, 105), min_swing_pct=3)
    assert pivots[-1].confirmed is False
    assert all(p.confirmed for p in pivots[:-1])


def test_평균_변화율은_계열_규모에_무관하다():
    """임계를 데이터에서 정할 때 쓰는 값 — 절대가격이 아니라 비율이어야 한다."""
    small = average_swing_pct([100, 102, 100, 102])
    large = average_swing_pct([10_000, 10_200, 10_000, 10_200])
    assert abs(small - large) < 1e-9


# --- 패턴 8종 ---------------------------------------------------------------

def test_헤드앤숄더를_찾는다():
    # 어깨 120 · 머리 140 · 어깨 121, 넥라인 105/104
    series = _series(100, 120, 105, 140, 104, 121, 100)
    assert "head_and_shoulders" in _names(series)


def test_역헤드앤숄더를_찾는다():
    series = _series(140, 120, 135, 100, 136, 121, 140)
    assert "inverse_head_and_shoulders" in _names(series)


def test_쌍봉을_찾는다():
    series = _series(100, 130, 105, 131, 100)
    assert "double_top" in _names(series)


def test_쌍바닥을_찾는다():
    series = _series(130, 100, 125, 101, 130)
    assert "double_bottom" in _names(series)


def test_베어트랩을_찾는다():
    """저점 100을 깨고 94까지 내려갔다가 다시 그 위로 회복."""
    series = _series(120, 100, 115, 94, 108)
    assert "bear_trap" in _names(series)


def test_불트랩을_찾는다():
    """고점 120을 넘어 127까지 갔다가 다시 그 아래로."""
    series = _series(100, 120, 105, 127, 112)
    assert "bull_trap" in _names(series)


def test_삼각수렴을_찾는다():
    series = _series(100, 140, 105, 130, 112, 122, 116)
    assert "triangle" in _names(series)


def test_상승채널을_찾는다():
    series = _series(100, 120, 110, 130, 120, 140)
    assert "rising_channel" in _names(series)


def test_하락채널을_찾는다():
    series = _series(140, 120, 130, 110, 120, 100)
    assert "falling_channel" in _names(series)


# --- 비탐지(오탐 방지) -------------------------------------------------------

def test_직선에서는_아무_형태도_찾지_않는다():
    assert detect([100 + i for i in range(60)]) == ()


def test_평평한_계열에서는_아무_형태도_찾지_않는다():
    assert detect([100.0] * 60) == ()


def test_너무_짧은_계열은_판정하지_않는다():
    assert detect([100, 110, 105]) == ()


def test_높이가_다른_두_봉우리는_쌍봉이_아니다():
    """130과 160은 같은 높이로 볼 수 없다 — 허용 오차를 넘긴다."""
    assert "double_top" not in _names(_series(100, 130, 105, 160, 100))


def test_머리가_솟지_않으면_헤드앤숄더가_아니다():
    """세 고점이 비슷하면 그건 머리가 없는 형태다."""
    assert "head_and_shoulders" not in _names(_series(100, 120, 105, 121, 104, 120, 100))


def test_되돌아오지_않으면_트랩이_아니다():
    """저점을 깨고 계속 내려가면 그냥 하락이다."""
    assert "bear_trap" not in _names(_series(120, 100, 110, 90, 85))


# --- 성질 -------------------------------------------------------------------

def test_같은_입력은_항상_같은_결과다():
    """난수를 쓰지 않는다 — 게임 쪽 결정론 게이트가 요구하는 성질이다."""
    series = _series(100, 120, 105, 140, 104, 121, 100)
    assert len({tuple(detect(series)) for _ in range(20)}) == 1


def test_신뢰도는_0과_1_사이이고_높은_순으로_정렬된다():
    series = _series(100, 120, 105, 140, 104, 121, 100)
    found = detect(series)
    assert found
    assert all(0.0 < p.confidence <= 1.0 for p in found)
    assert [p.confidence for p in found] == sorted(
        (p.confidence for p in found), reverse=True
    )


def test_좌표는_계열_범위_안을_가리킨다():
    """화면이 이 인덱스로 오버레이를 그린다 — 범위를 벗어나면 선이 엉뚱한 데 그려진다."""
    series = _series(100, 120, 105, 140, 104, 121, 100)
    for pattern in detect(series):
        assert 0 <= pattern.start_index <= pattern.end_index < len(series)
        for index, _price in pattern.points:
            assert 0 <= index < len(series)


def test_절대가격이_달라도_같은_형태를_찾는다():
    """비율로 판정해야 저가주와 고가주에 같은 규칙이 걸린다."""
    shape = (100, 120, 105, 140, 104, 121, 100)
    cheap = _names(_series(*shape))
    pricey = _names(_series(*(v * 1_000 for v in shape)))
    assert cheap == pricey
