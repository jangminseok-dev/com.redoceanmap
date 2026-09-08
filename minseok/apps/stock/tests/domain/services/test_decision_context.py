from datetime import date

from stock.domain.services.decision_context import Candidate, DecisionContext, HeldView, NewsCite, build_prompt


def test_프롬프트에_후보_보유_규칙_인용id가_들어간다():
    ctx = DecisionContext(
        as_of=date(2026, 8, 3), cash_krw=50_000_000, equity_krw=100_000_000,
        candidates=(Candidate("AAPL", "애플", 200.0, 0.03, "UP", 0.42, 0.58, 0.52, True, 0.018, "BULL", False, 0.3,
                              (NewsCite(7, "애플 실적 서프라이즈", 0.8, "earnings", date(2026, 8, 2)),)),),
        held=(HeldView("TSLA", "SHORT", 3, 250.0, 240.0, 0.04, 2),),
    )
    text = build_prompt(ctx)
    for needle in ("2026-08-03", "AAPL(애플)", "[news_id=7]", "TSLA SHORT 3주", "비중 ≤ 20%", '"orders"'):
        assert needle in text
    assert ctx.allowed_tickers == {"AAPL", "TSLA"} and ctx.allowed_news_ids == {7}
