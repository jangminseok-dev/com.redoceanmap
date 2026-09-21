"""종목 리포트 — 모델 서술 뒤에 코드가 데이터로 쓰는 근거 블록(순수 함수, LLM 없음).

2026-09-17 실사용: "샌디스크 분석해줘"·"엔비디아 분석해줘"의 답이 300자대 기술지표 두세 문장이었다. 가치·체력은
카드에만, 뉴스·과거 통계·매물대는 본문에 거의 안 나왔다. 여기서는 가진 수치를 판단 순서(가격 위치 → 추세·모멘텀 →
수급 → 거래 밀집 구간 → 과거 같은 신호 통계 → 가치·체력 → 뉴스)로 전부 풀어 쓴다.
권유 표현(매수·매도·목표가)은 쓰지 않는다 — 유사투자자문업 미신고. 해석은 "지표가 무엇을 뜻하나"까지만.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from chat.domain.services.report_format import aside, plain, section

# 채점기가 이 뒤(코드가 쓴 근거 블록)를 모델 서술의 인용·환각 판정에서 뺀다
STOCK_REPORT_HEADING = "**종목 리포트 — "


@dataclass(frozen=True)
class StockReportInput:
    symbol: str
    unit: str                                   # 원 | 달러
    price: float
    ma20: float | None = None
    ma50: float | None = None
    support: float | None = None                # 60일 저점
    resistance: float | None = None             # 60일 고점
    rsi: float | None = None
    bb_percent_b: float | None = None
    atr_pct: float | None = None
    volume_ratio: float | None = None
    obv_slope: float | None = None
    momentum_12_1: float | None = None
    poc_low: float | None = None
    poc_high: float | None = None
    poc_share: float | None = None
    forecast_ready: bool = False
    up_rate: float | None = None
    baseline_up_rate: float | None = None
    sample_size: int = 0
    fundamentals: tuple[tuple[str, str], ...] = ()                 # (tone, 문장)
    # 위험 신호(신호 보드와 같은 판정, 2026-09-17) — 보드에 없는 종목이면 None
    vol_state: str | None = None
    drawdown_risk: str | None = None
    rv20: float | None = None
    rv_percentile: float | None = None
    risk_evidence: tuple[str, ...] = ()                            # 이 상태의 검증 실측 문장
    news: tuple[tuple[str, datetime | None, float | None], ...] = field(default_factory=tuple)  # (제목, 발행, 감성)


def _p(value: float, unit: str) -> str:
    return f"{value:,.0f}{unit}" if unit == "원" else f"{value:,.2f}{unit}"


def _gap(price: float, ref: float) -> str:
    diff = (price / ref - 1) * 100
    return f"{abs(diff):.1f}% {'위' if diff >= 0 else '아래'}"


DETAIL_HEADING = "**세부 근거**"   # 프론트가 접힌 상태로 렌더한다(compare.DETAIL_HEADING과 같은 표기)


def _glance(r: StockReportInput) -> list[str]:
    """한눈에 — 지금 어디쯤·얼마나 흔들릴지·싼지/튼튼한지·뉴스 결. 방향 판단은 하지 않는다."""
    out = []
    if r.support and r.resistance and r.resistance > r.support:
        where = (r.price - r.support) / (r.resistance - r.support)
        zone = "고점 부근" if where >= 0.8 else "저점 부근" if where <= 0.2 else "중간"
        out.append(f"가격 위치 — 60일 범위의 {zone}({where:.0%})")
    if r.vol_state is not None:
        badge = ("큰 낙폭 위험 높음" if r.drawdown_risk == "HIGH" else "변동성 확대 가능성 높음" if r.vol_state == "HIGH"
                 else "안정 구간" if r.drawdown_risk == "LOW" else "변동성 낮음" if r.vol_state == "LOW" else "보통")
        out.append(f"위험 — 향후 20거래일 {badge}(검증된 위험 신호)")
    if r.fundamentals:
        warn = sum(1 for t, _ in r.fundamentals if t == "warning")
        good = sum(1 for t, _ in r.fundamentals if t == "positive")
        out.append(f"가치·체력 — 긍정 {good} · 경고 {warn}")
    tones = [s for _, _, s in r.news if s is not None]
    if tones:
        pos = sum(1 for s in tones if s > 0.2)
        neg = sum(1 for s in tones if s < -0.2)
        out.append(f"최근 뉴스 결 — 호재 성격 {pos} · 악재 성격 {neg} · 중립 {len(tones) - pos - neg}")
    return ["**한눈에**", *[f"- {line}" for line in out]] if out else []


def render_stock_report(r: StockReportInput) -> str:
    u = r.unit
    head = [f"{STOCK_REPORT_HEADING}{r.symbol}** (코드가 수치로 정리한 근거 — 매수·매도 판단이 아니에요)", *_glance(r)]
    lines = [DETAIL_HEADING]

    pos = [f"현재가 {_p(r.price, u)}"]
    if r.ma20:
        pos.append(f"20일 이동평균 {_p(r.ma20, u)}보다 **{_gap(r.price, r.ma20)}**")
    if r.ma50:
        pos.append(f"50일 이동평균 {_p(r.ma50, u)}보다 **{_gap(r.price, r.ma50)}**")
    if r.support and r.resistance and r.resistance > r.support:
        where = (r.price - r.support) / (r.resistance - r.support) * 100
        pos.append(f"60일 범위 {_p(r.support, u)}~{_p(r.resistance, u)} 중 아래에서 **{where:.0f}% 지점**")
    if r.ma20 and r.ma50:
        pos.append("20일선이 50일선 위(단기 흐름이 중기보다 강함)" if r.ma20 >= r.ma50 else "20일선이 50일선 아래(단기 흐름이 중기보다 약함)")
    lines += section("가격 위치", pos)

    trend = []
    if r.momentum_12_1 is not None:
        trend.append(f"12-1 모멘텀 {r.momentum_12_1:+.1%}")
        trend.append(aside("1년 전부터 한 달 전까지의 수익률 — 최근 한 달의 단기 변동은 뺀 중기 추세"))
    if r.rsi is not None:
        state = "과매수권(70 이상)" if r.rsi >= 70 else "과매도권(30 이하)" if r.rsi <= 30 else "중립권(30~70)"
        trend.append(f"RSI(14) **{r.rsi:.1f}** — {state}")
    if r.bb_percent_b is not None:
        band = "밴드 상단 돌파" if r.bb_percent_b > 1 else "밴드 하단 이탈" if r.bb_percent_b < 0 else "밴드 안"
        trend.append(f"볼린저 %B **{r.bb_percent_b:.2f}** — {band}")
    if r.atr_pct is not None:
        trend.append(f"하루 평균 변동폭(ATR) 가격의 {r.atr_pct:.1%}")
    lines += section("추세·변동성", trend)

    flow = []
    if r.volume_ratio is not None:
        shown = round(r.volume_ratio, 1)   # 표시값으로 판정 — "0.8배(평소보다 적음)"처럼 숫자와 말이 어긋나지 않게
        judge = "평소보다 많음" if shown >= 1.2 else "평소보다 적음" if shown < 0.8 else "평소 수준"
        flow.append(f"최근 5일 거래량 20일 평균의 {r.volume_ratio:.1f}배({judge})")
    if r.obv_slope is not None:
        flow.append(f"OBV 기울기 **{r.obv_slope:+.2f}** ({'거래량이 오르는 날에 더 실림' if r.obv_slope > 0 else '거래량이 내리는 날에 더 실림' if r.obv_slope < 0 else '방향 없음'})")
    lines += section("수급", flow)

    if r.poc_low is not None and r.poc_high is not None:
        share = f", 전체 거래량의 {r.poc_share:.0%}" if r.poc_share else ""
        side = "위" if r.price > r.poc_high else "아래" if r.price < r.poc_low else "안"
        lines += section("거래 밀집 구간", [
            f"**{_p(r.poc_low, u)}~{_p(r.poc_high, u)}**{share}",
            f"현재가는 그 {side}",
            aside("과거 거래가 몰린 가격대일 뿐 지지·저항선이 아니에요"),
        ])

    if r.vol_state is not None:
        badge = ("큰 낙폭 위험 높음" if r.drawdown_risk == "HIGH" else "변동성 확대 가능성 높음" if r.vol_state == "HIGH"
                 else "큰 낙폭 위험 낮음(안정 구간)" if r.drawdown_risk == "LOW" else "변동성 확대 가능성 낮음" if r.vol_state == "LOW"
                 else "보통")
        risk = [f"**{badge}**"]
        if r.rv20 is not None and r.rv_percentile is not None:
            risk.append(f"최근 20일 변동성 연 {r.rv20:.0%} — 이 종목 1년 중 {r.rv_percentile:.0%} 위치")
        risk += [plain(f"검증 실측 — {e}") for e in r.risk_evidence]
        risk.append(aside("방향이 아니라 흔들림의 크기 — 검증 구간에서도 유지된 신호"))
        lines += section("위험 신호(향후 20거래일)", risk)

    if r.sample_size:
        if r.forecast_ready and r.up_rate is not None and r.baseline_up_rate is not None:
            lines += section("과거 같은 신호 통계", [
                f"이후 상승 비율 **{r.up_rate:.0%}** — 평소 {r.baseline_up_rate:.0%}",
                aside(f"표본 {r.sample_size:,}건 · 과거 통계이지 이번 결과의 확률이 아니에요"),
            ])
        else:
            lines += section("과거 같은 신호 통계", [
                "평소와 구별되는 차이가 검증되지 않아 수치를 결론에 쓰지 않아요", aside(f"표본 {r.sample_size:,}건"),
            ], bold=False)

    if r.fundamentals:
        mark = {"positive": "○", "warning": "△", "neutral": "·"}
        lines += section("가치·체력", [f"{mark.get(t, '·')} {s}" for t, s in r.fundamentals])
    else:
        lines += section("가치·체력", ["수집된 재무 지표가 없어요"])

    if r.news:
        items = []
        for title, published, sentiment in r.news[:4]:
            tone = "" if sentiment is None else (" · 호재 성격" if sentiment > 0.2 else " · 악재 성격" if sentiment < -0.2 else " · 중립")
            date = f"{published:%m/%d}" if published else "날짜 미상"
            items.append(f"{title} _({date}{tone})_")
        lines += section("최근 뉴스", items, bold=False)
    return "\n".join(head) + "\n\n" + "\n".join(lines)
