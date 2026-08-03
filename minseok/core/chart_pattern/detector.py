"""차트 패턴 탐지 — 헤드앤숄더·더블탑·트랩 등 8종.

**하는 일과 하지 않는 일**

- 한다: 가격 계열에서 널리 쓰이는 형태를 찾아 좌표와 함께 돌려준다.
- 하지 않는다: 매수·매도 지시, 목표가, 상승·하락 확률. `note`는 그 형태가 통상 어떻게
  해석되는지를 적을 뿐이며 예측이 아니다. 호출자는 이 구분을 화면 문구에서도 지켜야 한다.

패턴은 전부 **극값의 순서와 높이 관계**로 정의되므로 `pivots.find_pivots()`가 뽑은 지그재그
위에서 매칭한다. 원계열을 직접 훑지 않는다 — 잡음 하나에 어깨가 생겼다 사라진다.

외부 의존이 없는 순수 계산이며 난수를 쓰지 않는다. 같은 입력은 항상 같은 결과다.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.chart_pattern.pivots import Pivot, average_swing_pct, find_pivots

# 피벗 임계의 기본값을 데이터에서 정할 때 쓰는 배수. 인접 변화율 평균의 몇 배를
# "의미 있는 스윙"으로 볼 것인가 — 작으면 노이즈가 피벗이 되고 크면 패턴이 사라진다.
SWING_MULTIPLIER = 2.5
MIN_SWING_FLOOR_PCT = 0.15  # 초저변동 계열에서 임계가 0으로 수렴하는 것을 막는다

# 두 고점(또는 두 저점)을 "같은 높이"로 볼 허용 오차. 패턴 진폭 대비 비율이다.
LEVEL_TOLERANCE = 0.30
# 헤드가 어깨보다 이만큼은 높아야 헤드로 인정한다(진폭 대비).
HEAD_PROMINENCE = 0.20


@dataclass(frozen=True)
class DetectedPattern:
    """탐지된 형태 하나.

    `points`는 화면이 넥라인·어깨를 그릴 좌표다(계열 인덱스, 가격). **인덱스 오름차순**이라
    호출자가 그대로 폴리라인 하나로 이을 수 있다.
    `confidence`는 **이상적 형태와의 기하학적 근접도**(0~1)이며 적중 확률이 아니다.
    """

    name: str          # head_and_shoulders 등 기계용 식별자
    label: str         # 화면 표시명
    start_index: int
    end_index: int
    confidence: float
    points: tuple[tuple[int, float], ...]
    note: str          # 통상적 해석 — 지시·예측이 아니다


def _points(*pivots: Pivot) -> tuple[tuple[int, float], ...]:
    """좌표를 인덱스 오름차순으로. 화면이 폴리라인 하나로 잇는 것을 전제한다."""
    return tuple(sorted(((p.index, p.price) for p in pivots), key=lambda point: point[0]))


def _closeness(a: float, b: float, span: float) -> float:
    """두 값이 얼마나 같은 높이인지(1=완전 일치, 0=허용 오차 끝). span은 패턴 진폭."""
    if span <= 0:
        return 0.0
    gap = abs(a - b) / span
    return max(0.0, 1.0 - gap / LEVEL_TOLERANCE)


def _recent_window(
    pivots: tuple[Pivot, ...], size: int, first_is_high: bool
) -> tuple[Pivot, ...] | None:
    """끝에서부터 `size`개 극값. 성격이 안 맞으면 한 칸 물러나 다시 본다.

    마지막 극값은 진행 중이라(`confirmed=False`) 완성된 형태의 뒤에 하나 더 붙는 일이
    잦다 — 그때 윈도가 한 칸 밀려 형태를 놓친다.
    """
    for offset in (0, 1):
        end = len(pivots) - offset
        start = end - size
        if start < 0:
            return None
        window = pivots[start:end]
        if window[0].is_high == first_is_high:
            return window
    return None


def _highs(pivots: tuple[Pivot, ...]) -> list[Pivot]:
    return [p for p in pivots if p.is_high]


def _lows(pivots: tuple[Pivot, ...]) -> list[Pivot]:
    return [p for p in pivots if not p.is_high]


def _head_and_shoulders(pivots: tuple[Pivot, ...], inverse: bool) -> DetectedPattern | None:
    """어깨-머리-어깨. 정방향은 고-저-고-저-고, 역방향은 그 반대다."""
    # 고-저-고-저-고 5개 극값(지그재그라 번갈아 나오는 것은 이미 보장된다)
    window = _recent_window(pivots, 5, first_is_high=not inverse)
    if window is None:
        return None

    left, trough1, head, trough2, right = window
    span = max(p.price for p in window) - min(p.price for p in window)
    if span <= 0:
        return None

    # 머리가 양 어깨보다 솟아 있어야 한다
    if inverse:
        prominent = head.price < min(left.price, right.price) - span * HEAD_PROMINENCE
    else:
        prominent = head.price > max(left.price, right.price) + span * HEAD_PROMINENCE
    if not prominent:
        return None

    shoulder_match = _closeness(left.price, right.price, span)
    neckline_match = _closeness(trough1.price, trough2.price, span)
    if shoulder_match <= 0 or neckline_match <= 0:
        return None

    return DetectedPattern(
        name="inverse_head_and_shoulders" if inverse else "head_and_shoulders",
        label="역헤드앤숄더" if inverse else "헤드앤숄더",
        start_index=left.index,
        end_index=right.index,
        confidence=round(min(1.0, (shoulder_match * 0.6 + neckline_match * 0.4)), 2),
        points=_points(*window),
        note=(
            "바닥에서 자주 언급되는 형태입니다. 두 저점을 이은 선이 넥라인입니다."
            if inverse
            else "고점에서 자주 언급되는 형태입니다. 두 저점을 이은 선이 넥라인입니다."
        ),
    )


def _double(pivots: tuple[Pivot, ...], bottom: bool) -> DetectedPattern | None:
    """더블탑/더블바텀 — 같은 높이의 극값 두 개와 그 사이 반대 극값."""
    window = _recent_window(pivots, 3, first_is_high=not bottom)
    if window is None:
        return None

    first, middle, second = window
    span = max(p.price for p in window) - min(p.price for p in window)
    if span <= 0:
        return None

    level_match = _closeness(first.price, second.price, span)
    if level_match <= 0:
        return None
    # 사이 극값이 충분히 파여야 두 봉우리로 읽힌다
    depth = abs(middle.price - (first.price + second.price) / 2) / span
    if depth < 0.5:
        return None

    return DetectedPattern(
        name="double_bottom" if bottom else "double_top",
        label="쌍바닥" if bottom else "쌍봉",
        start_index=first.index,
        end_index=second.index,
        confidence=round(min(1.0, level_match), 2),
        points=_points(*window),
        note=(
            "비슷한 높이의 저점이 두 번 나온 형태입니다."
            if bottom
            else "비슷한 높이의 고점이 두 번 나온 형태입니다."
        ),
    )


def _trap(pivots: tuple[Pivot, ...], values: list[float], bear: bool) -> DetectedPattern | None:
    """베어트랩/불트랩 — 직전 극값을 뚫었다가 되돌아온 형태.

    베어트랩: 이전 저점을 깨고 내려갔다가 그 위로 회복.
    불트랩: 이전 고점을 넘었다가 그 아래로 되돌아옴.
    """
    same_side = _lows(pivots) if bear else _highs(pivots)
    if len(same_side) < 2 or not values:
        return None

    prior, breakout = same_side[-2], same_side[-1]
    if breakout.index <= prior.index:
        return None
    # 뚫었는가
    broke = breakout.price < prior.price if bear else breakout.price > prior.price
    if not broke:
        return None
    # 되돌아왔는가 — 현재가가 이전 극값 반대편에 있어야 한다
    current = values[-1]
    recovered = current > prior.price if bear else current < prior.price
    if not recovered:
        return None

    span = abs(prior.price - breakout.price)
    if span <= 0 or prior.price == 0:
        return None
    # 이탈이 얕을수록, 회복이 깊을수록 전형적이다
    overshoot_pct = span / abs(prior.price) * 100.0
    recovery = abs(current - breakout.price) / span
    if overshoot_pct > 25.0:  # 이 정도면 되돌림이 아니라 추세 전환이다
        return None

    return DetectedPattern(
        name="bear_trap" if bear else "bull_trap",
        label="베어트랩" if bear else "불트랩",
        start_index=prior.index,
        end_index=len(values) - 1,
        confidence=round(min(1.0, recovery / 1.5), 2),
        points=_points(prior, breakout),
        note=(
            "직전 저점을 잠깐 깨고 다시 올라온 형태입니다."
            if bear
            else "직전 고점을 잠깐 넘고 다시 내려온 형태입니다."
        ),
    )


def _triangle(pivots: tuple[Pivot, ...]) -> DetectedPattern | None:
    """삼각수렴 — 고점은 낮아지고 저점은 높아져 폭이 좁아지는 형태."""
    highs, lows = _highs(pivots), _lows(pivots)
    if len(highs) < 2 or len(lows) < 2:
        return None
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    if not (h2.price < h1.price and l2.price > l1.price):
        return None

    early = h1.price - l1.price
    late = h2.price - l2.price
    if early <= 0 or late <= 0 or late >= early:
        return None

    return DetectedPattern(
        name="triangle",
        label="삼각수렴",
        start_index=min(h1.index, l1.index),
        end_index=max(h2.index, l2.index),
        confidence=round(min(1.0, 1.0 - late / early), 2),
        points=_points(h1, h2, l1, l2),
        note="고점과 저점의 폭이 좁아지는 구간입니다.",
    )


def _channel(pivots: tuple[Pivot, ...]) -> DetectedPattern | None:
    """추세채널 — 고점과 저점이 같은 방향으로 나란히 이동하는 형태."""
    highs, lows = _highs(pivots), _lows(pivots)
    if len(highs) < 2 or len(lows) < 2:
        return None
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]

    rising = h2.price > h1.price and l2.price > l1.price
    falling = h2.price < h1.price and l2.price < l1.price
    if not (rising or falling):
        return None

    early = h1.price - l1.price
    late = h2.price - l2.price
    if early <= 0 or late <= 0:
        return None
    # 폭이 유지돼야 채널이다. 크게 벌어지거나 좁아지면 다른 형태다.
    width_match = 1.0 - abs(late - early) / early
    if width_match < 0.5:
        return None

    return DetectedPattern(
        name="rising_channel" if rising else "falling_channel",
        label="상승채널" if rising else "하락채널",
        start_index=min(h1.index, l1.index),
        end_index=max(h2.index, l2.index),
        confidence=round(min(1.0, width_match), 2),
        points=_points(h1, h2, l1, l2),
        note="고점과 저점이 나란히 이동하는 구간입니다.",
    )


def detect(
    closes: list[float],
    min_swing_pct: float | None = None,
) -> tuple[DetectedPattern, ...]:
    """가격 계열에서 형태를 찾는다. 신뢰도 높은 순으로 돌려준다.

    `min_swing_pct`를 주지 않으면 계열의 평균 변화율에서 정한다 — 변동성이 종목마다
    몇 배씩 다르므로 고정 임계는 어떤 종목에서는 피벗을 0개로, 어떤 종목에서는 전부로 만든다.

    입력은 종가 하나면 된다. 고가·저가를 따로 받지 않는 이유는 패턴이 극값의 **관계**로
    정의되기 때문이고, 게임 쪽 틱 계열에는 애초에 봉이 없기 때문이다.
    """
    if len(closes) < 5:
        return ()

    swing = min_swing_pct
    if swing is None:
        swing = max(MIN_SWING_FLOOR_PCT, average_swing_pct(closes) * SWING_MULTIPLIER)

    pivots = find_pivots(closes, swing)
    if len(pivots) < 3:
        return ()

    found = [
        _head_and_shoulders(pivots, inverse=False),
        _head_and_shoulders(pivots, inverse=True),
        _double(pivots, bottom=False),
        _double(pivots, bottom=True),
        _trap(pivots, closes, bear=True),
        _trap(pivots, closes, bear=False),
        _triangle(pivots),
        _channel(pivots),
    ]
    return tuple(
        sorted(
            (p for p in found if p is not None and p.confidence > 0),
            key=lambda p: (-p.confidence, p.name),
        )
    )
