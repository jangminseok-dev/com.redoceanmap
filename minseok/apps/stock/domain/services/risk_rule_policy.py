"""위험 규칙 계정의 판단 — **검증된** 위험 신호만 쓰는 계정(2026-09-18 신설).

지표 규칙 계정(대조군)은 방향 신호를 따른다. 그 방향은 겹침 보정 재검증에서 최근 5년 평소와 구별되지 않았다.
반면 위험 신호(변동성 확대·큰 낙폭)는 같은 기준의 검증 구간에서도 유지됐다 — 다만 **방향이 아니라 흔들림의 크기**다.
그래서 이 계정은 "오를 종목 찍기"가 아니라 "위험한 자리를 피하면 결과가 나아지는가"를 기록한다:

- 진입: `drawdown_risk == LOW`(저변동 + 50>200·가격>50일선) 종목만 **롱**. 숏은 없다 — 하락을 맞히는 근거가 없다.
- 청산: 5거래일 보유 만료(지표 규칙 계정과 같은 지평) 또는 보유 중 `drawdown_risk == HIGH`로 바뀌면 조기 청산.
- 실적 발표 임박(earnings_veto)은 진입하지 않는다(대조군과 같은 규칙).
- 같은 층에서는 변동성 백분위가 낮은 순 — 검증 실측이 가장 좋은 쪽(20일 내 -10% 하락 15% vs 평소 24%)부터 담는다.

결정론이라 리플레이가 항상 같은 원장을 만든다. 상태 판정은 보드·주간 검증과 같은 도메인 함수(risk_signal)를 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass

from stock.domain.services import paper_rules as rules
from stock.domain.services.decision_context import Candidate, HeldView
from stock.domain.services.decision_parser import Order

ENTRY_WEIGHT = 1.0 / rules.assumed_max_positions
HOLD_SESSIONS = rules.assumed_signal_hold_sessions
SIGNAL_KEYS = ("risk_drawdown_low",)


@dataclass(frozen=True)
class RiskView:
    """판단 시점까지의 일봉으로 계산한 위험 상태 — 보드가 쓰는 것과 같은 값."""

    ticker: str
    vol_state: str          # HIGH | NORMAL | LOW
    drawdown_risk: str      # HIGH | NORMAL | LOW
    rv_percentile: float


def decide(candidates: tuple[Candidate, ...], held: tuple[HeldView, ...],
           risk: dict[str, RiskView]) -> tuple[Order, ...]:
    orders: list[Order] = []
    held_by = {h.ticker: h for h in held}

    for h in held:
        state = risk.get(h.ticker)
        turned_risky = state is not None and state.drawdown_risk == "HIGH"
        if h.sessions_held >= HOLD_SESSIONS or turned_risky:
            why = "낙폭 위험 높음으로 전환" if turned_risky else f"{HOLD_SESSIONS}거래일 보유 만료"
            orders.append(Order(h.ticker, "SELL", 0.0, why, (), SIGNAL_KEYS))

    open_slots = rules.assumed_max_positions - len(held)
    entries = [
        c for c in candidates
        if not c.earnings_veto and c.ticker not in held_by
        and (state := risk.get(c.ticker)) is not None and state.drawdown_risk == "LOW"
    ]
    entries.sort(key=lambda c: (risk[c.ticker].rv_percentile, c.ticker))
    for c in entries[: max(open_slots, 0)]:
        state = risk[c.ticker]
        orders.append(Order(
            c.ticker, "BUY", ENTRY_WEIGHT,
            f"낙폭 위험 낮음(변동성 1년 중 {state.rv_percentile:.0%} 위치·상승 추세)"
            " — 검증 구간 20일 내 -10% 하락 15% vs 평소 24%",
            (), SIGNAL_KEYS,
        ))
    return tuple(orders)
