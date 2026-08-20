"""뉴스 이벤트 사후 수익률 집계 — 순수 도메인 서비스.

hub CLAUDE가 *"라벨은 학습 피처, 정답은 실현 수익률(price_bars 조인)"*이라 선언해
놓고 구현이 없었다. 이벤트 유형별 실제 반응률이 한 번도 계산된 적이 없다.

**반드시 기준선 대비로 본다.** 절대 수익률만 보면 거짓 결론이 난다 — 실제로
7개 이벤트 유형의 5일 수익률이 전부 음수(−0.97% ~ −1.91%)로 나오는데, 이는
이벤트 효과가 아니라 표본 기간의 시장 방향이다. 전체 평균을 기준선으로 빼야
"이 이벤트가 남들보다 나은가"라는 질문에 답할 수 있다.

표본 독립성도 함께 본다 — 특정 주에 몰린 표본은 관측 수가 커도 사실상 하나다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

# 이 비율 이상이 한 주에 몰리면 독립 관측으로 보기 어렵다
CONCENTRATION_WARN = 0.5
# 버킷이 이 미만이면 수치를 신뢰하지 않는다(백테스트의 n≥100 규율과 같은 계열)
MIN_BUCKET_SAMPLES = 100


@dataclass(frozen=True)
class EventSample:
    """뉴스 1건 × 실현 수익률."""

    event_type: str
    sentiment: float
    return_pct: float
    week: str  # 발행 주(YYYY-MM-DD) — 표본 집중도 판정용


@dataclass(frozen=True)
class EventBucket:
    key: str
    n: int
    avg_return_pct: float
    excess_pct: float      # 기준선(전체 평균) 대비 — 이 값이 본체다
    positive_rate: float
    reliable: bool         # 표본이 충분한가


@dataclass(frozen=True)
class EventStudyReport:
    horizon_days: int
    total: int
    baseline_pct: float           # 전체 평균 = 같은 기간 시장 방향
    by_event: list[EventBucket]
    by_sentiment: list[EventBucket]
    top_week_share: float         # 가장 많이 몰린 주의 비중
    warnings: list[str]


def _bucket(key: str, values: list[float], baseline: float) -> EventBucket:
    n = len(values)
    avg = sum(values) / n
    return EventBucket(
        key=key,
        n=n,
        avg_return_pct=round(avg, 3),
        excess_pct=round(avg - baseline, 3),
        positive_rate=round(sum(1 for v in values if v > 0) / n, 3),
        reliable=n >= MIN_BUCKET_SAMPLES,
    )


def _sentiment_band(sentiment: float) -> str:
    if sentiment >= 0.5:
        return "강한 긍정"
    if sentiment > 0:
        return "약한 긍정"
    if sentiment == 0:
        return "중립"
    if sentiment > -0.5:
        return "약한 부정"
    return "강한 부정"


@dataclass(frozen=True)
class _Core:
    """일간·장중이 공유하는 집계 결과 — 지평 단위만 다르고 판정 규칙은 같다."""

    total: int
    baseline_pct: float
    by_event: list[EventBucket]
    by_sentiment: list[EventBucket]
    top_week_share: float
    warnings: list[str]


@dataclass(frozen=True)
class ShortHorizonReport:
    """분 단위 지평 — 5분봉으로 재는 발행 직후 반응.

    일간 리포트와 같은 규칙(기준선 대비·표본 집중도)으로 읽는다. 다른 것은 지평 단위와,
    **측정 가능한 구간이 5분봉 보유 기간에 갇힌다**는 점뿐이다(`coverage_note`).
    """

    horizon_minutes: int
    total: int
    baseline_pct: float
    by_event: list[EventBucket]
    by_sentiment: list[EventBucket]
    top_week_share: float
    warnings: list[str]
    coverage_note: str


def _core(samples: list[EventSample]) -> _Core:
    returns = [s.return_pct for s in samples]
    baseline = sum(returns) / len(returns)

    by_event_raw: dict[str, list[float]] = defaultdict(list)
    by_sent_raw: dict[str, list[float]] = defaultdict(list)
    for s in samples:
        by_event_raw[s.event_type].append(s.return_pct)
        by_sent_raw[_sentiment_band(s.sentiment)].append(s.return_pct)

    weeks = Counter(s.week for s in samples)
    top_week_share = weeks.most_common(1)[0][1] / len(samples)

    warnings = []
    if top_week_share >= CONCENTRATION_WARN:
        warnings.append(
            f"표본의 {top_week_share:.0%}가 한 주({weeks.most_common(1)[0][0]})에 몰려 있습니다 — "
            "횡단면 상관이 커 독립 관측으로 보기 어렵습니다."
        )
    if not any(len(v) >= MIN_BUCKET_SAMPLES for v in by_event_raw.values()):
        warnings.append(f"모든 이벤트 유형의 표본이 {MIN_BUCKET_SAMPLES}건 미만입니다.")

    return _Core(
        total=len(samples),
        baseline_pct=round(baseline, 3),
        by_event=sorted(
            (_bucket(k, v, baseline) for k, v in by_event_raw.items()),
            key=lambda b: -b.excess_pct,
        ),
        by_sentiment=sorted(
            (_bucket(k, v, baseline) for k, v in by_sent_raw.items()),
            key=lambda b: -b.excess_pct,
        ),
        top_week_share=round(top_week_share, 3),
        warnings=warnings,
    )


def aggregate(samples: list[EventSample], horizon_days: int) -> EventStudyReport:
    """이벤트 유형·감성대별 사후 수익률을 기준선 대비로 집계한다(일 단위 지평)."""
    if not samples:
        return EventStudyReport(
            horizon_days=horizon_days, total=0, baseline_pct=0.0,
            by_event=[], by_sentiment=[], top_week_share=0.0,
            warnings=["표본이 없습니다."],
        )
    c = _core(samples)
    return EventStudyReport(
        horizon_days=horizon_days,
        total=c.total,
        baseline_pct=c.baseline_pct,
        by_event=c.by_event,
        by_sentiment=c.by_sentiment,
        top_week_share=c.top_week_share,
        warnings=c.warnings,
    )


def aggregate_intraday(
    samples: list[EventSample], horizon_minutes: int, coverage_note: str
) -> ShortHorizonReport:
    """발행 직후 분 단위 반응 — 5분봉 기준.

    `coverage_note`는 호출자가 만든다(어느 날짜부터 5분봉이 있는지는 DB가 아는 사실이라
    순수 도메인이 알 수 없다). 이 문장이 리포트에 남아야 "왜 표본이 이것뿐인가"에 답이 된다.
    """
    if not samples:
        return ShortHorizonReport(
            horizon_minutes=horizon_minutes, total=0, baseline_pct=0.0,
            by_event=[], by_sentiment=[], top_week_share=0.0,
            warnings=["표본이 없습니다."], coverage_note=coverage_note,
        )
    c = _core(samples)
    return ShortHorizonReport(
        horizon_minutes=horizon_minutes,
        total=c.total,
        baseline_pct=c.baseline_pct,
        by_event=c.by_event,
        by_sentiment=c.by_sentiment,
        top_week_share=c.top_week_share,
        warnings=c.warnings,
        coverage_note=coverage_note,
    )
