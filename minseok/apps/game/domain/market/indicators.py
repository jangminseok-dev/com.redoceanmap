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
