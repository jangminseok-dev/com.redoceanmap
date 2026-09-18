"""위험 규칙 계정 — 검증된 낙폭 위험 신호만 쓰는 판단(2026-09-18)."""
from stock.domain.services import paper_rules as rules
from stock.domain.services.decision_context import Candidate, HeldView
from stock.domain.services.risk_rule_policy import RiskView, decide


def _cand(ticker, earnings_veto=False):
    return Candidate(ticker=ticker, name=ticker, last_close=100.0, return_5d_pct=None, direction="NEUTRAL",
                     score=None, up_rate=None, baseline_up_rate=None, ready=False, atr_pct=0.02, regime=None,
                     earnings_veto=earnings_veto, sentiment_3d=None)


def _held(ticker, sessions_held, side="LONG"):
    return HeldView(ticker=ticker, side=side, quantity=10, avg_price=100.0,
                    last_close=101.0, unrealized_pct=1.0, sessions_held=sessions_held)


def _risk(ticker, drawdown, pct=0.1, vol="LOW"):
    return RiskView(ticker=ticker, vol_state=vol, drawdown_risk=drawdown, rv_percentile=pct)


def test_낙폭_위험_낮음만_롱으로_담고_변동성_낮은_순이다():
    cands = (_cand("A"), _cand("B"), _cand("C"))
    risk = {"A": _risk("A", "LOW", 0.18), "B": _risk("B", "LOW", 0.05), "C": _risk("C", "HIGH", 0.95, "HIGH")}
    orders = decide(cands, (), risk)
    assert [o.ticker for o in orders] == ["B", "A"]          # 변동성 백분위 낮은 순
    assert {o.action for o in orders} == {"BUY"}             # 숏 없음 — 하락을 맞히는 근거가 없다
    assert orders[0].weight == 1.0 / rules.assumed_max_positions
    assert "검증 구간" in orders[0].reason


def test_위험_상태를_모르는_종목은_담지_않는다():
    assert decide((_cand("A"),), (), {}) == ()


def test_실적_발표_임박은_진입하지_않는다():
    assert decide((_cand("A", earnings_veto=True),), (), {"A": _risk("A", "LOW")}) == ()


def test_보유_중_낙폭_위험_높음이면_조기_청산한다():
    orders = decide((), (_held("A", 1),), {"A": _risk("A", "HIGH", 0.92, "HIGH")})
    assert [(o.ticker, o.action) for o in orders] == [("A", "SELL")] and "낙폭 위험 높음" in orders[0].reason


def test_보유_만료면_청산하고_안전하면_계속_들고_간다():
    keep = decide((), (_held("A", 1),), {"A": _risk("A", "LOW")})
    assert keep == ()
    expire = decide((), (_held("A", rules.assumed_signal_hold_sessions),), {"A": _risk("A", "LOW")})
    assert [o.action for o in expire] == ["SELL"] and "보유 만료" in expire[0].reason
