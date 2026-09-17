from __future__ import annotations

from stock.domain.entities.fundamental_snapshot import FundamentalSnapshot
from stock.domain.value_objects.insight_vo import Insight

# 임계값 — 일반적 밸류에이션 관례 수준. 업종 벤치마크가 없으므로 단정 대신 '권' 표현을 쓴다.
# 저PER·저PBR은 긍정(강조색)이 아니라 중립이다(2026-09-17) — 자체 백테스트(_docs/FUNDAMENTAL_BACKTEST_2026-08.md)에서
# 저평가 5분위(Q1)의 초과수익이 PER·PBR 모두 음수로 게이트 미달이었다. "싸 보인다"를 좋은 신호처럼 칠하지 않는다.
LOW_VALUE_CAVEAT = " 다만 이 워치리스트 백테스트에서는 이런 종목이 평균보다 더 오르지 않았어요."
PER_LOW = 8.0
PER_HIGH = 30.0
PBR_LOW = 1.0
PBR_HIGH = 5.0
ROE_GOOD = 0.15   # 15%
ROE_POOR = 0.05   # 5%


def narrate(snapshots: list[FundamentalSnapshot]) -> list[Insight]:
    """소스별 스냅샷을 필드별 병합(dart 우선)해 해석 문장을 만든다.

    debt_to_equity는 소스별 단위(%/배수)가 혼재해 해석하지 않는다.
    """
    per = _merged(snapshots, "per")
    pbr = _merged(snapshots, "pbr")
    roe = _merged(snapshots, "roe")

    insights: list[Insight] = []
    if per is not None:
        if per <= 0:
            insights.append(Insight(
                key="per", tone="warning",
                text=f"PER {per:.1f} — 이익이 적자라 이익 기준 밸류에이션이 성립하지 않습니다.",
            ))
        elif per < PER_LOW:
            insights.append(Insight(
                key="per", tone="neutral",
                text=f"PER {per:.1f}배 — 이익 대비 주가가 낮은 편입니다.{LOW_VALUE_CAVEAT}",
            ))
        elif per > PER_HIGH:
            insights.append(Insight(
                key="per", tone="warning",
                text=f"PER {per:.1f}배 — 이익 대비 주가가 높은 편(고평가권 또는 높은 성장 기대)입니다.",
            ))
    if pbr is not None and pbr > 0:
        if pbr < PBR_LOW:
            insights.append(Insight(
                key="pbr", tone="neutral",
                text=f"PBR {pbr:.2f}배 — 회사 장부가치보다 주가가 낮습니다.{LOW_VALUE_CAVEAT}",
            ))
        elif pbr > PBR_HIGH:
            insights.append(Insight(
                key="pbr", tone="warning",
                text=f"PBR {pbr:.2f}배 — 장부가치 대비 주가가 크게 높은 편입니다.",
            ))
    if roe is not None:
        if roe >= ROE_GOOD:
            insights.append(Insight(
                key="roe", tone="positive",
                text=f"ROE {roe * 100:.1f}% — 자기자본으로 이익을 잘 내는 편입니다.",
            ))
        elif roe < ROE_POOR:
            insights.append(Insight(
                key="roe", tone="warning",
                text=f"ROE {roe * 100:.1f}% — 자본 대비 이익 창출력이 낮은 편입니다.",
            ))
    return insights


def _merged(snapshots: list[FundamentalSnapshot], field: str) -> float | None:
    """필드별 병합 — dart(자체 계산) 우선, 없으면 yfinance."""
    for source in ("dart", "yfinance"):
        for s in snapshots:
            if s.source == source:
                value = getattr(s, field)
                if value is not None:
                    return value
    return None
