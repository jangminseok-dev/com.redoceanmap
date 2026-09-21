"""결론 한 줄 — 방향 신호 + 과거 통계를 하나로 말한다.

프론트 `www/lib/verdict.ts`의 Python 미러. 채팅 카드가 페이지 히어로와 **같은 결론**을 쓰도록
같은 규칙을 둔다(둘이 어긋나면 "상승 36% vs 평소와 다르지 않음"처럼 서로 반박). 순수 함수 —
외부 의존 없음. 파리티는 test_verdict.py가 대표 입력으로 고정한다.

중립(2026-09-21): 방향 판정의 73%가 중립이라 "지금은 방향을 말하기 어렵습니다"가 네 번 중 세 번 떴고,
"지표들이 서로 상쇄돼"는 중립의 26%에서만 사실이었다(하락 판정은 검증 실패로 꺼져 있어 점수가 뚜렷이
음수여도 중립이다). 중립을 점수 구간으로 나눠도 이후 상승 비율이 50~52%로 같아 방향을 더 말하는 건 답이 아니다.
그래서 중립이면 **검증된 위험 상태**(stock risk_signal)를 결론으로 앞세우고, 방향은 실제 이유를 한 문장으로 내린다.
"""
from __future__ import annotations

import math

from hub.app.dtos.stock_forecast_dto import StockForecastSummary, StockRiskSummary

# 확률이 기준선을 이 정도(%p)는 넘어야 "평소와 다르다"고 말한다 — verdict.ts와 동일
EDGE_MIN_PP = 3

# 종합 점수가 이 안쪽이면 "지표가 서로 상쇄됐다"고 말한다 — verdict.ts와 동일
OFFSET_BAND = 0.1

_WORD = {"UP": "상승", "DOWN": "하락", "NEUTRAL": "중립"}

# 위험 상태의 결과 문구 — 검증 리포트 키(stock risk_signal_backtester)별. verdict.ts와 동일
_OUTCOME = {
    "drop_high": "20거래일 안에 -10% 이상 떨어진 적이 있는 비율이",
    "drop_low": "20거래일 안에 -10% 이상 떨어진 적이 있는 비율이",
    "vol_high": "20거래일 안에 변동성이 더 커진 비율이",
    "vol_low": "20거래일 안에 변동성이 더 커진 비율이",
}


def _pct(v: float) -> int:
    """0~1 비율 → 반올림 정수 %. JS Math.round와 동일(0.5 올림)하게 맞춰 파리티 보장."""
    return math.floor(v * 100 + 0.5)


def _direction_note(score: float | None, up_threshold: float | None) -> str:
    """중립인 실제 이유 — 상쇄 / 하락 쪽(미검증이라 말하지 않음) / 상승 쪽 기준 미달 / 관망 규칙."""
    if score is None:
        return "방향은 과거 검증에서 평소와 구별되지 않아 말하지 않아요."
    t = up_threshold or 0.3
    if abs(score) <= OFFSET_BAND:
        return "방향 지표는 서로 상쇄돼 어느 쪽으로도 기울지 않았어요."
    if score < 0:
        return "방향 지표는 하락 쪽이지만, 하락 신호는 과거 검증을 통과하지 못해 방향으로 말하지 않아요."
    if score < t:
        return f"방향 지표는 상승 쪽이지만 기준에 못 미쳐요(점수 {score:.2f} · 기준 {t:.2f})."
    return "방향 점수는 기준을 넘었지만 관망 규칙(실적 발표·변동성·거래량)에 걸려 방향으로 말하지 않아요."


def _risk_lead(risk: StockRiskSummary) -> tuple[str, str, str | None]:
    """(headline, 상태 설명, 검증 리포트 키) — 낙폭이 변동성보다 먼저(보드 배지와 같은 우선순위)."""
    top = max(1, 100 - _pct(risk.rv_percentile))
    if risk.drawdown_risk == "HIGH":
        return "큰 낙폭 위험이 평소보다 높은 상태예요", "변동성이 크고 주가가 200일선 아래예요.", "drop_high"
    if risk.vol_state == "HIGH":
        return ("앞으로 20거래일, 평소보다 크게 출렁일 가능성이 높은 상태예요",
                f"최근 변동성이 자기 1년 중 상위 {top}%예요.", "vol_high")
    if risk.drawdown_risk == "LOW":
        return "큰 낙폭 위험이 평소보다 낮은 안정 구간이에요", "변동성이 낮고 상승 추세예요.", "drop_low"
    if risk.vol_state == "LOW":
        return ("당분간 크게 출렁일 가능성이 낮은 상태예요",
                f"최근 변동성이 자기 1년 중 하위 {max(1, _pct(risk.rv_percentile))}%예요.", "vol_low")
    return "변동성·낙폭 위험은 평소 수준이에요", f"최근 변동성이 자기 1년 분포의 중간쯤(상위 {top}%)이에요.", None


def _neutral(forecast: StockForecastSummary | None, score: float | None, up_threshold: float | None) -> tuple[str, str]:
    note = _direction_note(score, up_threshold)
    risk = forecast.risk if forecast else None
    if risk is None:  # 봉이 모자라 위험 상태를 못 낸 종목 — 방향 이유만이라도 정확히
        return ("지금은 방향을 말하기 어렵습니다", note)
    headline, state, key = _risk_lead(risk)
    parts = [state]
    proof = next((e for e in risk.evidence if e.key == key), None)
    if proof is not None:
        parts.append(f"과거 이 상태에서 {_OUTCOME[proof.key]} {_pct(proof.test_rate)}%였어요(평소 {_pct(proof.base_rate)}%).")
    parts.append(note)
    return (headline, " ".join(parts))


def verdict(
    direction: str, forecast: StockForecastSummary | None,
    score: float | None = None, up_threshold: float | None = None,
) -> tuple[str, str]:
    """(headline, detail) — 방향(analyze) + 확률 요약(forecast)으로 결론 문장을 만든다.
    score·up_threshold는 중립의 실제 이유를 가르는 데만 쓴다."""
    edge_pp: int | None = None
    if forecast and forecast.up_rate is not None and forecast.baseline_up_rate is not None:
        edge_pp = _pct(forecast.up_rate) - _pct(forecast.baseline_up_rate)
    word = _WORD.get(direction, "중립")

    if direction == "NEUTRAL":
        return _neutral(forecast, score, up_threshold)

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
