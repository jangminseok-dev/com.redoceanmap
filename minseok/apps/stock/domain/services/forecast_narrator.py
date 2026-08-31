from __future__ import annotations

from stock.domain.value_objects.backtest_report import MIN_SIGNAL_SAMPLES
from stock.domain.value_objects.forecast_distribution import DirectionStats
from stock.domain.value_objects.insight_vo import Insight
from stock.domain.value_objects.position_profile import PositionProfile

QUANTILE_MIN_SAMPLES = 30  # 이 미만이면 분위수 밴드 대신 ATR 콘 폴백

_DIRECTION_LABELS = {"UP": "상승", "DOWN": "하락", "NEUTRAL": "중립(관망)"}
_REGIME_LABELS = {"BULL": "강세장", "BEAR": "약세장", "HIGH_VOL": "고변동성 국면"}
_RSI_ZONE_LABELS = {"oversold": "과매도 구간", "neutral": "중립 구간", "overbought": "과매수 구간"}


def narrate(
    direction: str,
    stats: DirectionStats,
    baseline_up_rate: float,
    horizon_days: int,
    ready: bool,
    regime: str | None = None,
    regime_conditional: bool = False,
    earnings_veto: bool = False,
    position: PositionProfile | None = None,
) -> list[Insight]:
    """확률·밴드의 근거를 초보자 문장으로 — 항상 '과거 통계' 한계를 병기한다."""
    insights: list[Insight] = []

    if position is not None:
        insights.append(_position_insight(position))

    if earnings_veto:
        insights.append(Insight(
            key="earnings", tone="warning",
            text=(
                "실적 발표 임박/직후(±2일)라 관망으로 강등했습니다 — "
                "이 구간은 기술 지표보다 발표 내용이 주가를 지배합니다."
            ),
        ))

    if regime is not None:
        label = _REGIME_LABELS.get(regime, regime)
        if regime_conditional:
            insights.append(Insight(
                key="regime", tone="neutral",
                text=(
                    f"현재 시장은 {label}(SPY 200일선·VIX 기준) — "
                    "아래 통계는 같은 국면의 과거 신호만으로 계산했습니다."
                ),
            ))
        else:
            insights.append(Insight(
                key="regime", tone="neutral",
                text=(
                    f"현재 시장은 {label}이지만 같은 국면의 표본이 부족해 "
                    "전체 기간 통계를 사용했습니다."
                ),
            ))

    if stats.sample_size > 0:
        up_pct = round(stats.hits / stats.sample_size * 100)
        base_pct = round(baseline_up_rate * 100)
        if direction == "NEUTRAL":
            lead = "과거 이 종목이 지금처럼 뚜렷한 방향 신호가 없던(중립) 날들 기준 — "
        else:
            lead = f"과거 이 종목에 지금과 같은 {_DIRECTION_LABELS[direction]} 신호가 났을 때 — "
        compare = "높습니다" if up_pct > base_pct else ("낮습니다" if up_pct < base_pct else "같습니다")
        insights.append(Insight(
            key="probability", tone="neutral",
            text=(
                f"{lead}{stats.sample_size}회 중 {stats.hits}회({up_pct}%)가 "
                f"{horizon_days}거래일 뒤 상승 마감했습니다. 평소 상승률 {base_pct}%보다 {compare}. "
                "과거 통계이며 미래를 보장하지 않습니다."
            ),
        ))

    if not ready:
        if direction == "NEUTRAL":
            text = "중립 신호의 통계는 방향 예측이 아니라 참고용입니다."
        else:
            text = (
                f"표본 {stats.sample_size}회 — 통계적 확신 기준(표본 {MIN_SIGNAL_SAMPLES}회 이상 + "
                "신뢰구간이 평소 상승률과 뚜렷이 구분)을 충족하지 못해 참고용입니다."
            )
        insights.append(Insight(key="sample", tone="warning", text=text))

    if stats.sample_size < QUANTILE_MIN_SAMPLES:
        insights.append(Insight(
            key="band", tone="neutral",
            text="같은 신호 표본이 적어 예측 범위는 실적 분포 대신 변동성(ATR) 기반으로 그렸습니다.",
        ))
    elif stats.median is not None:
        insights.append(Insight(
            key="band", tone="neutral",
            text=(
                f"차트의 예측 범위는 같은 신호 {stats.sample_size}회의 {horizon_days}일 뒤 "
                f"실적 분포입니다 — 중앙값 {stats.median * 100:+.1f}%, "
                f"가운데 절반이 {stats.q25 * 100:+.1f}%~{stats.q75 * 100:+.1f}% 사이였습니다."
            ),
        ))

    insights.extend(_downside_insights(stats, horizon_days))

    insights.append(Insight(
        key="basis", tone="neutral",
        text=(
            "이 통계는 기술 지표 신호(과매도·볼린저 밴드·모멘텀)만으로 계산했습니다 — "
            "뉴스 감성은 반영되지 않습니다. 하락 방향은 검증된 신호가 없어 예측하지 않고, "
            "아래 하방 통계로만 알려드립니다."
        ),
    ))
    return insights


def _position_insight(p: PositionProfile) -> Insight:
    """지금 어느 국면인가 — 낙폭·지지선 여력·RSI 구간. 예측이 아니라 현재 상태 서술."""
    zone = _RSI_ZONE_LABELS.get(p.rsi_zone, p.rsi_zone)
    drop = p.drawdown_from_high_pct * 100
    room = p.above_support_pct * 100
    # 고점 대비 낙폭이 일 변동성(ATR)의 몇 배인지 — "평소 흔들림인지 진짜 조정인지"의 눈금.
    # 주어를 명시한다 — "…의 5배입니다"만 남으면 무엇의 배수인지 읽을 수 없다(2026-08-31 실측).
    scale = ""
    if p.atr_pct > 0 and drop < 0:
        scale = (
            f" 이 낙폭은 하루 평균 변동폭({p.atr_pct * 100:.1f}%)의 "
            f"{abs(drop) / (p.atr_pct * 100):.0f}배입니다."
        )
    return Insight(
        key="position", tone="neutral",
        text=(
            f"현재 60일 고점 대비 {drop:+.1f}%, 60일 저점보다 {room:+.1f}% 위에 있습니다. "
            f"RSI {p.rsi:.0f}({zone}).{scale}"
        ),
    )


def _downside_insights(stats: DirectionStats, horizon_days: int) -> list[Insight]:
    """얼마나 더 빠질 수 있고 회복은 얼마나 됐나 — 방향 단정 없이 실측 분포만.

    하락 방향 예측은 인샘플·홀드아웃 두 구간 연속 통과 조합이 없어 채택하지 않았다
    (BACKTEST_RESCORE_2026-07). 그래서 "떨어진다"가 아니라 "같은 신호에서 이랬다"로만 말한다.
    """
    out: list[Insight] = []
    if stats.sample_size == 0 or stats.trough_median_pct is None:
        return out

    down_pct = f"{stats.down_close_rate * 100:.0f}%" if stats.down_close_rate is not None else "—"
    worst = (
        f", 나쁜 쪽 25%는 {stats.trough_q25_pct * 100:+.1f}%"
        if stats.trough_q25_pct is not None else ""
    )
    out.append(Insight(
        key="downside", tone="neutral",
        text=(
            f"같은 신호 {stats.sample_size}회의 {horizon_days}거래일 구간에서 "
            f"장중 최대 낙폭은 중앙값 {stats.trough_median_pct * 100:+.1f}%{worst}였습니다. "
            f"{horizon_days}일 뒤 하락 마감은 {down_pct}."
        ),
    ))

    if stats.dip_samples == 0:
        out.append(Insight(
            key="recovery", tone="neutral",
            text="같은 신호에서는 구간 중 기준가 아래로 내려간 사례가 없었습니다.",
        ))
    elif stats.recovery_rate is not None:
        days = (
            f" 회복까지 중앙값 {stats.recovery_days_median:.0f}거래일."
            if stats.recovery_days_median is not None else ""
        )
        out.append(Insight(
            key="recovery", tone="neutral",
            text=(
                f"기준가 아래로 내려갔던 {stats.dip_samples}회 중 "
                f"{stats.recovery_rate * 100:.0f}%가 {horizon_days}일 안에 기준가를 회복했습니다.{days}"
            ),
        ))
    return out
