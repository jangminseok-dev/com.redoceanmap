"""차트 보조지표 — 이동평균·RSI (순수 계산).

**서버가 계산해서 내려준다.** 프론트는 가격을 만들지 않는다(game-harness §1-6)는 규칙이
지표에도 그대로 적용된다 — 화면이 스스로 평균을 내면 백엔드가 보는 값과 갈라질 수 있고,
그러면 같은 종목을 두 화면이 다르게 설명하게 된다.

입력은 **일별 종가 배열**이다. 봉(OHLC)이 아니라 종가만 쓰는 이유는 비용이다 — 봉 하나는
60틱을 훑어야 하지만 종가는 1틱이면 된다(실측: 240일 봉 148ms vs 종가 5.7ms). 이동평균
120일선을 그리려면 화면 밖으로 120일을 더 봐야 하는데, 봉으로 하면 그 워밍업만으로 예산을
넘긴다.
"""
from __future__ import annotations

# 화면에 그리는 이동평균 기간(게임일). 토스·키움 등 국내 증권 앱의 기본값과 같다.
MA_PERIODS = (5, 20, 60, 120)
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STDDEV = 2.0
ATR_PERIOD = 14
VOLUME_SHORT = 5
VOLUME_LONG = 20


def moving_average(closes: list[int], period: int) -> list[float | None]:
    """단순이동평균. 표본이 모자란 앞 구간은 `None`이다.

    `None`을 0으로 채우지 않는다 — 0으로 채우면 차트가 바닥에서 치솟는 가짜 선을 그린다.
    """
    if period <= 0:
        raise ValueError("기간은 1 이상이어야 한다")
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period:
        return out
    window = sum(closes[:period])
    out[period - 1] = window / period
    for i in range(period, len(closes)):
        window += closes[i] - closes[i - period]
        out[i] = window / period
    return out


def rsi(closes: list[int], period: int = RSI_PERIOD) -> list[float | None]:
    """상대강도지수(0~100). Wilder 평활을 쓴다 — 국내 증권 앱의 기본 구현이다.

    첫 `period`개는 `None`이다. 상승·하락이 한쪽뿐인 구간에서 100/0이 나오는 것은
    지표의 정의대로이며 이상치가 아니다.
    """
    if period <= 0:
        raise ValueError("기간은 1 이상이어야 한다")
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        # Wilder 평활 — 지수이동평균의 α = 1/period 형태다
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0  # 무변동 구간은 중립
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def bollinger_percent_b(closes: list[int], period: int = BB_PERIOD, k: float = BB_STDDEV) -> float | None:
    """볼린저 밴드 안에서의 위치(0=하단, 1=상단). 표본이 모자라면 `None`.

    밴드 폭이 0인 구간(완전 무변동)은 0.5로 둔다 — 0으로 나누지 않으면서 "중립"이 맞다.
    """
    if len(closes) < period:
        return None
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((v - mean) ** 2 for v in window) / period
    sigma = variance**0.5
    if sigma == 0:
        return 0.5
    lower = mean - k * sigma
    upper = mean + k * sigma
    return (closes[-1] - lower) / (upper - lower)


def atr_pct(
    closes: list[int], lows: list[int], highs: list[int], period: int = ATR_PERIOD
) -> float | None:
    """평균 실체범위 ÷ 현재가(%). 표본이 모자라면 `None`.

    전일 종가를 쓰는 True Range 정의를 그대로 따른다 — 갭을 변동으로 세지 않으면
    하루 안에서만 흔들린 종목과 갭으로 뛴 종목이 같아 보인다.
    """
    if len(closes) < period + 1 or len(lows) != len(closes) or len(highs) != len(closes):
        return None
    ranges = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(len(closes) - period, len(closes))
    ]
    if closes[-1] <= 0:
        return None
    return sum(ranges) / period / closes[-1] * 100.0


def volume_ratio(volumes: list[int], short: int = VOLUME_SHORT, long: int = VOLUME_LONG) -> float | None:
    """최근 단기 평균 거래량 ÷ 장기 평균. 1.0이면 평소만큼 거래됐다는 뜻이다."""
    if len(volumes) < long:
        return None
    long_avg = sum(volumes[-long:]) / long
    if long_avg <= 0:
        return None
    return sum(volumes[-short:]) / short / long_avg


def obv_slope(closes: list[int], volumes: list[int], window: int = VOLUME_LONG) -> float | None:
    """OBV(누적 거래량)의 최근 기울기를 총거래량으로 정규화한 값(-1~1 부근).

    "오르는 날 거래가 실렸는가"를 본다. 절대 OBV는 종목마다 자릿수가 달라 비교가 안 되므로
    창 안 총거래량으로 나눈다.
    """
    if len(closes) != len(volumes) or len(closes) < window + 1:
        return None
    obv = 0.0
    series = []
    for i in range(len(closes) - window, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv -= volumes[i]
        series.append(obv)
    total = sum(volumes[-window:])
    if total <= 0:
        return None
    return (series[-1] - series[0]) / total
