"""종목 상태 분해 — 지금 이 종목이 어떤 상태인가 (game-strategy §3-1).

⚠️ **예측이 아니다.** 이 게임의 주가는 브라운 운동 + 뉴스 충격으로 만든 값이라 과거 형태에
미래 정보가 담겨 있지 않다. 여기서 내는 점수는 **현재 상태의 요약**이며, 높다고 오를 확률이
높다는 뜻이 아니다. 화면 문구도 이 구분을 지켜야 한다(차트 패턴의 `note`와 같은 규칙).

그럼 왜 만드는가: 유저가 36종목을 훑을 때 "이 종목이 지금 과열인지 눌려 있는지, 거래가
실렸는지, 뉴스가 걸려 있는지"를 한눈에 보려면 축이 필요하다. 지표를 화면에 늘어놓고
해석을 유저에게 떠넘기는 대신, 같은 임계값으로 일관되게 요약해 준다.

**부호 규약: 양수 = 뜨겁다(많이 올랐다·과매수·거래 몰림·호재), 음수 = 차갑다.**
이걸 한 방향으로 고정하는 것이 이 파일의 핵심이다 — 추세는 "정배열=강세"로, RSI는
"과매수=되돌림"으로 읽는 식으로 섞으면 축끼리 부호가 반대가 되어 가중 합이 의미를 잃는다
(실제로 첫 구현이 그랬다: 정배열 +1과 과매수 -1이 서로를 상쇄해 과열 종목이 "눌림"으로 나왔다).
어느 쪽이 유리한지는 **말하지 않는다** — 랜덤워크라 그런 답이 존재하지 않는다.

**stock 앱의 분석과 계산을 공유하지 않는 이유**: 저쪽은 실데이터라 펀더멘털·LLM 뉴스 라벨이
축에 들어가고 입력 계약이 그 도메인 VO에 묶여 있다(스포크끼리 직접 참조도 금지다).
반대로 게임에는 저쪽에 없는 축이 있다 — **뉴스가 결정론이라 "그 뉴스가 지금 가격을 얼마나
밀고 있는지"를 추정이 아니라 정확히 안다.** 축이 다르면 같은 계산이 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 축별 가중치 — 합 1.0. 계수 교체 지점(game-harness §5-3).
WEIGHT_TREND = 0.30      # 이동평균 배열
WEIGHT_MOMENTUM = 0.25   # RSI
WEIGHT_POSITION = 0.20   # 볼린저 밴드 내 위치
WEIGHT_FLOW = 0.10       # 거래량·OBV
WEIGHT_NEWS = 0.15       # 창 안 뉴스의 실제 가격 기여

RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
# 뉴스 기여를 -1~1로 누르는 기준(로그 공간). 이보다 크면 포화된다 —
# 밈 스퀴즈 한 방(즉시 28%)이 다른 축을 전부 덮지 않게 한다.
NEWS_SATURATION = 0.12


@dataclass(frozen=True)
class SignalAxis:
    key: str        # trend | momentum | position | flow | news
    label: str
    value: float    # -1.0 ~ 1.0 원신호
    weight: float
    note: str       # 이 축이 지금 무엇을 말하는지(해석 문장, 예측 아님)


@dataclass(frozen=True)
class SymbolSignal:
    score: float                  # -1.0 ~ 1.0 가중 합
    label: str                    # 과열 | 달아오름 | 잠잠 | 식는 중 | 침체
    axes: tuple[SignalAxis, ...]  # 기여도 분해 — 점수만 보여주면 근거가 사라진다


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _trend_axis(ma_short: float | None, ma_long: float | None, price: int) -> SignalAxis | None:
    """단기선이 장기선 위인가, 그리고 현재가가 그 위인가."""
    if ma_short is None or ma_long is None or ma_long <= 0:
        return None
    spread = (ma_short - ma_long) / ma_long
    # 현재가와 단기선의 이격도 **연속값**으로 본다. `price >= ma_short`로 ±1을 주면
    # 1원 차이로 부호가 튀고, 무엇보다 완전히 평평한 종목(가격=단기선=장기선)이
    # +0.3을 받아 "달아오름"으로 읽힌다.
    above = _clamp((price - ma_short) / ma_short / 0.02) if ma_short > 0 else 0.0
    # 이격 5%를 최대치로 본다 — 그 이상은 방향이 이미 분명하다
    value = _clamp(0.7 * _clamp(spread / 0.05) + 0.3 * above)
    if value > 0.3:
        note = "단기선이 장기선 위에 있고 현재가도 그 위입니다(정배열)"
    elif value < -0.3:
        note = "단기선이 장기선 아래로 내려와 있습니다(역배열)"
    else:
        note = "이동평균선이 서로 얽혀 방향이 분명하지 않습니다"
    return SignalAxis("trend", "추세", value, WEIGHT_TREND, note)


def _momentum_axis(rsi: float | None) -> SignalAxis | None:
    """RSI. 부호 규약대로 **과매수가 양수**다(뜨겁다)."""
    if rsi is None:
        return None
    if rsi >= RSI_OVERBOUGHT:
        value = _clamp((rsi - RSI_OVERBOUGHT) / (100.0 - RSI_OVERBOUGHT))
        note = f"RSI {rsi:.0f} — 과매수 구간입니다"
    elif rsi <= RSI_OVERSOLD:
        value = -_clamp((RSI_OVERSOLD - rsi) / RSI_OVERSOLD)
        note = f"RSI {rsi:.0f} — 과매도 구간입니다"
    else:
        value = 0.0
        note = f"RSI {rsi:.0f} — 중립 구간입니다"
    return SignalAxis("momentum", "과열·침체", value, WEIGHT_MOMENTUM, note)


def _position_axis(percent_b: float | None) -> SignalAxis | None:
    """볼린저 밴드 안 위치. 상단에 붙어 있으면 뜨겁다(양수) — 부호 규약을 따른다."""
    if percent_b is None:
        return None
    value = _clamp((percent_b - 0.5) * 2.0)
    if percent_b > 0.9:
        note = "볼린저 상단에 붙어 있습니다"
    elif percent_b < 0.1:
        note = "볼린저 하단에 붙어 있습니다"
    else:
        note = "볼린저 밴드 중앙부에 있습니다"
    return SignalAxis("position", "밴드 위치", value, WEIGHT_POSITION, note)


def _flow_axis(volume_ratio: float | None, obv_slope: float | None) -> SignalAxis | None:
    """거래가 실렸는가. 거래량만으로는 방향을 모르므로 OBV 기울기와 함께 본다."""
    if volume_ratio is None and obv_slope is None:
        return None
    surge = _clamp(((volume_ratio or 1.0) - 1.0) / 1.0)
    direction = _clamp((obv_slope or 0.0) * 3.0)
    # 거래가 터졌어도 방향이 없으면 0에 가깝다 — 크기와 방향의 곱이다
    value = _clamp(direction * (0.5 + 0.5 * abs(surge)))
    flow_word = "매수" if direction > 0.1 else "매도" if direction < -0.1 else "양방향"
    if (volume_ratio or 1.0) > 1.5:
        note = f"거래량이 평소의 {volume_ratio:.1f}배 — {flow_word} 쪽에 실렸습니다"
    elif (volume_ratio or 1.0) < 0.7:
        note = f"거래가 한산합니다 — 실린 쪽은 {flow_word}입니다"
    else:
        note = f"거래량은 평소 수준 — 실린 쪽은 {flow_word}입니다"
    return SignalAxis("flow", "수급", value, WEIGHT_FLOW, note)


def _news_axis(news_impact_log: float, headline_count: int) -> SignalAxis:
    """창 안 뉴스가 **지금 가격에 실제로 넣고 있는 값**.

    stock 앱은 기사 감성을 LLM으로 추정하지만, 이 게임은 이벤트가 결정론이라 기여를
    그대로 합산할 수 있다 — 추정이 아니라 실제 값이다.
    """
    value = _clamp(news_impact_log / NEWS_SATURATION)
    if headline_count == 0:
        note = "이 종목에 걸린 최근 뉴스가 없습니다"
    elif value > 0.2:
        note = f"최근 뉴스 {headline_count}건이 가격을 밀어 올리고 있습니다"
    elif value < -0.2:
        note = f"최근 뉴스 {headline_count}건이 가격을 끌어내리고 있습니다"
    else:
        note = f"최근 뉴스 {headline_count}건은 이미 영향이 거의 소멸했습니다"
    return SignalAxis("news", "뉴스", value, WEIGHT_NEWS, note)


def _label(score: float) -> str:
    """상태 이름. **어느 쪽이 유리한지는 말하지 않는다** — 랜덤워크라 그런 답이 없다."""
    if score >= 0.35:
        return "과열"
    if score >= 0.12:
        return "달아오름"
    if score > -0.12:
        return "잠잠"
    if score > -0.35:
        return "식는 중"
    return "침체"


def evaluate(
    *,
    price_krw: int,
    ma_short: float | None,
    ma_long: float | None,
    rsi: float | None,
    percent_b: float | None,
    volume_ratio: float | None,
    obv_slope: float | None,
    news_impact_log: float,
    headline_count: int,
) -> SymbolSignal:
    """축을 모아 하나의 요약으로. 계산할 수 없는 축(표본 부족)은 **빠지고 가중치도 빠진다** —
    0으로 채우면 시즌 초반에 모든 종목이 중립으로 보인다.
    """
    axes = [
        axis
        for axis in (
            _trend_axis(ma_short, ma_long, price_krw),
            _momentum_axis(rsi),
            _position_axis(percent_b),
            _flow_axis(volume_ratio, obv_slope),
            _news_axis(news_impact_log, headline_count),
        )
        if axis is not None
    ]
    total_weight = sum(a.weight for a in axes)
    score = (
        sum(a.value * a.weight for a in axes) / total_weight if total_weight > 0 else 0.0
    )
    return SymbolSignal(score=round(score, 4), label=_label(score), axes=tuple(axes))
