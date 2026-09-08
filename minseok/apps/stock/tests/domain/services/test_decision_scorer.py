from stock.domain.services.decision_scorer import score_entry


def test_롱은_상승_적중_숏은_하락_적중_변동성_초과_기준():
    # ATR 2% × √5 × 0.25 ≈ 1.12% 문턱
    up = score_entry(action="BUY", reason_kind="news", ticker="A", entry_price=100, exit_close=102, atr_pct=0.02)
    assert up.hit is True and up.realized_return_pct == 0.02
    tiny = score_entry(action="BUY", reason_kind="news", ticker="A", entry_price=100, exit_close=100.5, atr_pct=0.02)
    assert tiny.hit is False
    short = score_entry(action="SHORT", reason_kind="indicator", ticker="A", entry_price=100, exit_close=98, atr_pct=0.02)
    assert short.hit is True and short.realized_return_pct == -0.02


def test_ATR_없으면_부호_판정으로_열화():
    assert score_entry(action="BUY", reason_kind="none", ticker="A", entry_price=100, exit_close=100.01, atr_pct=None).hit is True
