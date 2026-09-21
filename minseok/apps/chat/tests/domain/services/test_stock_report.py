from datetime import datetime

from chat.domain.services.stock_report import STOCK_REPORT_HEADING, StockReportInput, render_stock_report


def _input(**kw):
    base = dict(symbol="SNDK", unit="달러", price=1519.97, ma20=1579.58, ma50=1507.79, support=998.19, resistance=2348.0,
                rsi=47.0, bb_percent_b=0.35, atr_pct=0.041, volume_ratio=0.8, obv_slope=-0.12, momentum_12_1=18.834,
                poc_low=1400.0, poc_high=1500.0, poc_share=0.18, sample_size=320,
                fundamentals=(("warning", "PBR 16.48배 — 장부가치 대비 주가가 크게 높은 편입니다."),),
                news=(("샌디스크 실적 발표", datetime(2026, 9, 15), 0.6),))
    base.update(kw)
    return StockReportInput(**base)


def test_종목_리포트는_가격_위치부터_뉴스까지_판단_순서로_푼다():
    text = render_stock_report(_input())
    assert text.startswith(f"{STOCK_REPORT_HEADING}SNDK**")
    heads = ["**가격 위치**", "**추세·변동성**", "**수급**", "**거래 밀집 구간**", "**과거 같은 신호 통계**", "**가치·체력**", "**최근 뉴스**"]
    idx = [text.index(h) for h in heads]
    assert idx == sorted(idx)
    assert "  - 20일 이동평균 1,579.58달러보다 **3.8% 아래**" in text
    assert "  - 60일 범위 998.19달러~2,348.00달러 중 아래에서 **39% 지점**" in text
    assert "  - 12-1 모멘텀 **+1883.4%**" in text and "  - RSI(14) **47.0** — 중립권" in text
    assert "**20일**" not in text and "**5일**" not in text   # 기간 표시를 값으로 굵게 하지 않는다
    assert "  - 최근 5일 거래량 20일 평균의 **0.8배**(평소 수준)" in text
    assert "현재가는 그 위" in text
    assert "평소와 구별되는 차이가 검증되지 않아" in text   # ready=False면 비율을 결론에 쓰지 않는다
    assert "  - 샌디스크 실적 발표 _(09/15 · 호재 성격)_" in text


def test_권유_표현을_쓰지_않는다():
    text = render_stock_report(_input(forecast_ready=True, up_rate=0.62, baseline_up_rate=0.51))
    assert "이번 결과의 확률이 아니에요" in text
    for word in ("매수하", "매도하", "사세요", "파세요", "목표가"):
        assert word not in text


def test_위험_신호가_있으면_검증_실측과_함께_싣는다():
    text = render_stock_report(_input(vol_state="HIGH", drawdown_risk="HIGH", rv20=0.72, rv_percentile=0.93,
                                      risk_evidence=("20거래일 안에 한 번이라도 -10% 이상 하락 30%(평소 24%)",)))
    assert ("- **위험 신호(향후 20거래일)**\n  - **큰 낙폭 위험 높음**\n  - 최근 20일 변동성 연 **72%** — 이 종목 1년 중 93% 위치\n"
            "  - 검증 실측 — 20거래일 안에 한 번이라도 -10% 이상 하락 30%(평소 24%)") in text
    assert text.index("**수급**") < text.index("**위험 신호") < text.index("**과거 같은 신호 통계**")
