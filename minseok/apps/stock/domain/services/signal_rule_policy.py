"""검증된 지표 규칙 계정의 판단 — EXAONE의 정직한 대조군.

스냅샷 방향을 그대로 따른다: UP → 롱 진입, DOWN → 숏 진입, 보유 5거래일 뒤 청산,
보유 중 반대 신호면 조기 청산. 실적 발표 임박(earnings_veto)은 진입하지 않는다.
결정론이라 리플레이가 항상 같은 원장을 만든다.
"""
from __future__ import annotations

from stock.domain.services import paper_rules as rules
from stock.domain.services.decision_context import Candidate, HeldView
from stock.domain.services.decision_parser import Order

ENTRY_WEIGHT = 1.0 / rules.assumed_max_positions


def decide(candidates: tuple[Candidate, ...], held: tuple[HeldView, ...]) -> tuple[Order, ...]:
    orders: list[Order] = []
    held_by = {h.ticker: h for h in held}
    direction = {c.ticker: c.direction for c in candidates}

    for h in held:
        opposite = (h.side == "LONG" and direction.get(h.ticker) == "DOWN") or (
            h.side == "SHORT" and direction.get(h.ticker) == "UP"
        )
        if h.sessions_held >= rules.assumed_signal_hold_sessions or opposite:
            why = "반대 신호" if opposite else f"{rules.assumed_signal_hold_sessions}거래일 보유 만료"
            orders.append(
                Order(h.ticker, "SELL" if h.side == "LONG" else "COVER", 0.0, why, (), ("snapshot_direction",))
            )

    open_slots = rules.assumed_max_positions - len(held)
    entries = [
        c for c in candidates
        if c.direction in ("UP", "DOWN") and not c.earnings_veto and c.ticker not in held_by
    ]
    # 신호가 뚜렷한 순 — 보드 정렬과 같은 뜻
    entries.sort(key=lambda c: (-(abs(c.score or 0.0)), c.ticker))
    for c in entries[: max(open_slots, 0)]:
        orders.append(
            Order(
                c.ticker,
                "BUY" if c.direction == "UP" else "SHORT",
                ENTRY_WEIGHT,
                f"스냅샷 {c.direction} 신호(score {c.score:+.2f})" if c.score is not None else f"스냅샷 {c.direction} 신호",
                (),
                ("snapshot_direction",),
            )
        )
    return tuple(orders)
