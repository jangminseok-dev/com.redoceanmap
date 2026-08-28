"""결론 한 줄 — 방향 신호 + 과거 통계를 하나로 말한다.

프론트 `www/lib/verdict.ts`의 Python 미러. 채팅 카드가 페이지 히어로와 **같은 결론**을 쓰도록
같은 규칙을 둔다(둘이 어긋나면 "상승 36% vs 평소와 다르지 않음"처럼 서로 반박). 순수 함수 —
외부 의존 없음. 파리티는 test_verdict.py가 대표 입력으로 고정한다.
"""
from __future__ import annotations

import math

from hub.app.dtos.stock_forecast_dto import StockForecastSummary

# 확률이 기준선을 이 정도(%p)는 넘어야 "평소와 다르다"고 말한다 — verdict.ts와 동일
EDGE_MIN_PP = 3

_WORD = {"UP": "상승", "DOWN": "하락", "NEUTRAL": "중립"}


def _pct(v: float) -> int:
    """0~1 비율 → 반올림 정수 %. JS Math.round와 동일(0.5 올림)하게 맞춰 파리티 보장."""
    return math.floor(v * 100 + 0.5)


def verdict(direction: str, forecast: StockForecastSummary | None) -> tuple[str, str]:
    """(headline, detail) — 방향(analyze) + 확률 요약(forecast)으로 결론 문장을 만든다."""
    edge_pp: int | None = None
    if forecast and forecast.up_rate is not None and forecast.baseline_up_rate is not None:
        edge_pp = _pct(forecast.up_rate) - _pct(forecast.baseline_up_rate)
    word = _WORD.get(direction, "중립")

    if direction == "NEUTRAL":
        return ("지금은 방향을 말하기 어렵습니다", "지표들이 서로 상쇄돼 한쪽으로 기울지 않았습니다.")

    # `up_rate`는 **그 방향의 적중률**이다(2026-08-28) — UP이면 변동성 초과 상승,
    # DOWN이면 초과 하락 비율. 기준선도 같은 방향의 것이라 우위는 양쪽 다 양수가 정상이다.
    moved = "올랐" if direction == "UP" else "내렸"

    if edge_pp is None or not (forecast and forecast.ready) or abs(edge_pp) < EDGE_MIN_PP:
        if edge_pp is None:
            detail = "과거 통계로 검증할 표본이 아직 없습니다."
        else:
            sign = "+" if edge_pp >= 0 else ""
            detail = (
                f"과거 같은 신호일 때 실제로 {moved}던 비율이 평소와 사실상 같았습니다"
                f"(차이 {sign}{edge_pp}%p)."
            )
        return (f"{word} 쪽 신호가 있지만, 근거는 약합니다", detail)

    sign = "+" if edge_pp >= 0 else ""
    return (
        f"{word} 쪽 신호이고, 과거 이 신호일 때 실제로 {moved}던 비율이 "
        f"평소보다 {sign}{edge_pp}%p 높았습니다",
        f"표본 {forecast.sample_size}회 · 95% 구간 {_pct(forecast.ci_low)}~{_pct(forecast.ci_high)}%.",
    )


def strength(score: float, up_threshold: float) -> str:
    """신호 세기 — "확신도 36%"는 초보자가 확률로 오독한다. 방향 임계값의 1·2배로 약/보통/강."""
    s = abs(score)
    t = up_threshold or 0.3
    if s < t:
        return "약"
    if s < t * 2:
        return "보통"
    return "강"
