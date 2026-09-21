"""감성 서프라이즈 신호의 예측력 검증 — 되살릴지 말지를 정하는 월례 채점(순수 도메인, 2026-09-21).

분석의 방향 점수는 한때 감성 서프라이즈(최근 7일 기사 라벨 평균 − 30일 평균)를 가중치 0.2로 얹었다. 화면이 쓰던 그대로
재검증하니 무신호였다(6/15~9/18·81종목·4,475건: 같은 날 두 종목을 견줘 값이 높은 쪽이 이후 수익률도 높았던 비율 50.4%(5일)·
50.1%(20일), 월마다 부호가 바뀜) — 그래서 뺐다. 다만 촘촘한 뉴스가 2026-07부터 2.7개월치뿐이라 "없다"고 단정하기엔 짧다.
이 모듈은 같은 검증을 매달 되풀이해, **아래 조건을 넘을 때만** 되살리기를 검토하게 한다. 넘기 전에는 가중치 0이 맞다.

채점 방식이 짝 비교인 이유: 방향 점수에 얹는다는 건 "서프라이즈가 큰 종목이 작은 종목보다 낫다"는 주장이다. 같은 날의 종목끼리만
견주므로 그 기간의 시장 방향(전체가 오르던 장)은 상쇄된다.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

RECENT_DAYS = 7          # StockInteractor.RECENT_SENTIMENT_DAYS와 같은 창
BASELINE_DAYS = 30
MIN_RECENT = 3           # StockInteractor.MIN_RECENT_SAMPLES
MIN_BASELINE = 5         # StockInteractor.MIN_BASELINE_SAMPLES

# 되살림 검토 조건 — 전부 넘어야 한다. 숫자는 2026-09-21에 정한 기준이고, 넘기 전에 고치지 않는다(결과를 보고 기준을 옮기면 검증이 아니다).
GATE_MIN_MONTHS = 6            # 표본이 충분한 달이 이만큼 쌓여야 한다
GATE_MIN_MONTH_OBS = 200       # 한 달의 관측(종목×거래일)이 이보다 적으면 그 달은 세지 않는다
GATE_MIN_HIT_RATE = 0.53       # 전체 짝 비교 적중률
GATE_MIN_CONSISTENT = 5        # 최근 GATE_MIN_MONTHS개월 중 적중률이 50%를 넘은 달 수


@dataclass(frozen=True)
class MonthResult:
    month: str            # "2026-08"
    observations: int
    pairs: int
    hit_rate: float | None


@dataclass(frozen=True)
class SurpriseStudy:
    horizon_days: int
    observations: int
    dates: int
    pairs: int
    hit_rate: float | None        # 값이 높은 쪽이 이후 수익률도 높았던 비율
    months: list[MonthResult]
    ready: bool                   # 되살림 검토 조건 충족
    verdict: str


def _rolling_mean(days: list[date], sums: list[float], counts: list[int], end: date, window: int) -> tuple[float | None, int]:
    """end를 포함한 최근 window일의 라벨 평균과 기사 수 — days는 오름차순."""
    lo = bisect_right(days, end - timedelta(days=window))
    hi = bisect_right(days, end)
    n = sum(counts[lo:hi])
    return (sum(sums[lo:hi]) / n if n else None), n


def surprise_series(daily: list[tuple[str, date, float, int]]) -> dict[str, dict[date, float]]:
    """(종목, 발행일, 감성 합, 기사 수) → 종목별 {날짜: 서프라이즈}. 화면과 같은 최소 표본을 못 넘는 날은 뺀다."""
    by_ticker: dict[str, list[tuple[date, float, int]]] = defaultdict(list)
    for ticker, day, total, n in daily:
        by_ticker[ticker].append((day, total, n))
    out: dict[str, dict[date, float]] = {}
    for ticker, rows in by_ticker.items():
        rows.sort()
        days, sums, counts = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
        series: dict[date, float] = {}
        day, last = days[0], days[-1] + timedelta(days=RECENT_DAYS)
        while day <= last:
            recent, rn = _rolling_mean(days, sums, counts, day, RECENT_DAYS)
            base, bn = _rolling_mean(days, sums, counts, day, BASELINE_DAYS)
            if recent is not None and base is not None and rn >= MIN_RECENT and bn >= MIN_BASELINE:
                series[day] = max(-1.0, min(1.0, recent - base))
            day += timedelta(days=1)
        out[ticker] = series
    return out


def _pair_hits(points: list[tuple[float, float]]) -> tuple[int, int]:
    hits = total = 0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            dx, dy = points[i][0] - points[j][0], points[i][1] - points[j][1]
            if dx == 0 or dy == 0:
                continue
            total += 1
            hits += (dx > 0) == (dy > 0)
    return hits, total


def study(daily: list[tuple[str, date, float, int]], closes: dict[str, list[tuple[date, float]]], horizon_days: int) -> SurpriseStudy:
    """서프라이즈 → horizon_days 거래일 뒤 수익률. closes는 종목별 (거래일, 종가) 오름차순."""
    surprises = surprise_series(daily)
    by_day: dict[date, list[tuple[float, float]]] = defaultdict(list)
    for ticker, bars in closes.items():
        series = surprises.get(ticker)
        if not series:
            continue
        for k in range(len(bars) - horizon_days):
            day, close = bars[k]
            s = series.get(day)
            if s is not None and close > 0:
                by_day[day].append((s, bars[k + horizon_days][1] / close - 1))

    month_hits: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])   # 적중 · 짝 · 관측
    for day, points in by_day.items():
        h, t = _pair_hits(points)
        m = month_hits[f"{day:%Y-%m}"]
        m[0] += h; m[1] += t; m[2] += len(points)
    months = [MonthResult(k, v[2], v[1], (v[0] / v[1] if v[1] else None)) for k, v in sorted(month_hits.items())]
    hits, pairs = sum(v[0] for v in month_hits.values()), sum(v[1] for v in month_hits.values())
    hit_rate = hits / pairs if pairs else None

    solid = [m for m in months if m.observations >= GATE_MIN_MONTH_OBS and m.hit_rate is not None]
    recent = solid[-GATE_MIN_MONTHS:]
    consistent = sum(1 for m in recent if m.hit_rate > 0.5)
    ready = (len(solid) >= GATE_MIN_MONTHS and hit_rate is not None and hit_rate >= GATE_MIN_HIT_RATE
             and consistent >= GATE_MIN_CONSISTENT)
    shown = f"{hit_rate:.1%}" if hit_rate is not None else "산출 불가"
    if ready:
        verdict = (f"되살림 검토 조건 충족 — 표본 충분한 달 {len(solid)}개, 짝 비교 적중 {shown}, "
                   f"최근 {len(recent)}개월 중 {consistent}개월이 50% 초과")
    else:
        verdict = (f"가중치 0 유지 — 표본 충분한 달 {len(solid)}/{GATE_MIN_MONTHS}개, 짝 비교 적중 {shown}"
                   f"(기준 {GATE_MIN_HIT_RATE:.0%}), 최근 {len(recent)}개월 중 {consistent}개월이 50% 초과(기준 {GATE_MIN_CONSISTENT})")
    return SurpriseStudy(horizon_days, sum(len(p) for p in by_day.values()), len(by_day), pairs, hit_rate, months, ready, verdict)
