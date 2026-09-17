"""위험 신호 — 향후 20거래일의 변동성 확대·큰 낙폭 가능성을 일봉 종가로 판정한다(순수 도메인, 2026-09-17).

신호 보드 재설계의 근거: 겹침 보정 재검증에서 **방향**(오를까 내릴까) 신호는 최근 5년 평소와 구별되지 않았다.
같은 83종목·같은 기준(~2020 학습 / 2021~ 검증, 유효 표본 n/20)으로 위험 쪽을 시험하니 검증 구간에서도 유지됐다:
- 현재 변동성이 자기 1년 분포 상위 20% → 20일 안에 변동성이 자기 70분위를 넘는 비율 51% vs 평소 33%(1.57배)
- 하위 20% → 17%(0.52배) · 변동성 순위 월별 순위상관 0.74(68개월 전부 양수)
- 저변동 + 상승 추세 → 20일 안에 -10% 이상 하락 15% vs 평소 24%(0.63배). 고변동 + 200일선 아래 → 30%(1.22배, 약함)
변동성 군집(최근 크게 움직인 종목이 계속 크게 움직인다)은 학계에서 오래 확인된 성질이라 방향과 달리 재현된다.

실시간 보드(`state_at`)와 주간 백테스트(`states`)가 **같은 증분 계산**을 쓴다 — 정의가 갈라지면 검증 수치가 보드와 맞지 않는다.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

VOL_WINDOW = 20            # 실현 변동성 창(거래일)
RANK_WINDOW = 252          # 자기 분포 창(약 1년)
RANK_MIN = 200             # 분포가 이만큼 쌓여야 백분위를 낸다
HIGH_PCT = 0.8
LOW_PCT = 0.2
MA_SHORT = 50
MA_LONG = 200
HORIZON = 20               # 검증 결과 창
DROP_THRESHOLD = -0.10     # 큰 낙폭 기준
OUTCOME_QUANTILE = 0.7     # 변동성 확대 결과 = 향후 20일 변동성이 판정일 자기 분포 70분위 초과
ANNUAL = math.sqrt(252)


@dataclass(frozen=True)
class RiskState:
    rv20: float                 # 최근 20일 실현 변동성(연율, 0.35 = 35%)
    rv_percentile: float        # 자기 1년 분포 안 위치(0~1, 평균 순위)
    vol_state: str              # HIGH | NORMAL | LOW
    trend: str                  # UP(50>200·가격>50) | DOWN(가격<200) | MIXED
    drawdown_risk: str          # HIGH(고변동·200일선 아래) | LOW(저변동·상승 추세) | NORMAL
    rv_q70: float               # 판정일 자기 분포 70분위(연율) — 결과 채점 기준


def _quantile(sorted_vals: list[float], q: float) -> float:
    """pandas 기본(linear) 분위수."""
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def states(closes: list[float]) -> list[RiskState | None]:
    """종가 시계열(과거 → 최신)의 날마다 위험 상태. 창이 덜 찬 날은 None."""
    n = len(closes)
    out: list[RiskState | None] = [None] * n
    rets: list[float] = [math.nan] + [
        math.log(closes[i] / closes[i - 1]) if closes[i - 1] > 0 and closes[i] > 0 else math.nan
        for i in range(1, n)
    ]
    rv_hist: list[float] = []          # 날짜 순 rv(최근 RANK_WINDOW개)
    rv_sorted: list[float] = []
    ma_s = ma_l = 0.0
    for i in range(n):
        ma_s += closes[i]
        ma_l += closes[i]
        if i >= MA_SHORT:
            ma_s -= closes[i - MA_SHORT]
        if i >= MA_LONG:
            ma_l -= closes[i - MA_LONG]
        if i < VOL_WINDOW:
            continue
        window = rets[i - VOL_WINDOW + 1:i + 1]
        if any(math.isnan(r) for r in window):
            continue
        mean = sum(window) / VOL_WINDOW
        rv = math.sqrt(sum((r - mean) ** 2 for r in window) / (VOL_WINDOW - 1)) * ANNUAL
        rv_hist.append(rv)
        bisect.insort(rv_sorted, rv)
        if len(rv_hist) > RANK_WINDOW:
            old = rv_hist.pop(0)
            del rv_sorted[bisect.bisect_left(rv_sorted, old)]
        if len(rv_hist) < RANK_MIN or i + 1 < MA_LONG:
            continue
        left = bisect.bisect_left(rv_sorted, rv)
        right = bisect.bisect_right(rv_sorted, rv)
        pct = (left + (right - left + 1) / 2) / len(rv_sorted)
        vol_state = "HIGH" if pct >= HIGH_PCT else "LOW" if pct <= LOW_PCT else "NORMAL"
        price, m50, m200 = closes[i], ma_s / MA_SHORT, ma_l / MA_LONG
        trend = "UP" if m50 > m200 and price > m50 else "DOWN" if price < m200 else "MIXED"
        risk = ("HIGH" if vol_state == "HIGH" and trend == "DOWN"
                else "LOW" if vol_state == "LOW" and trend == "UP" else "NORMAL")
        out[i] = RiskState(rv, pct, vol_state, trend, risk, _quantile(rv_sorted, OUTCOME_QUANTILE))
    return out


def state_at(closes: list[float]) -> RiskState | None:
    """최신 봉 기준 위험 상태 — 보드용. 봉이 모자라면 None."""
    if len(closes) < MA_LONG + 1 or len(closes) < RANK_MIN + VOL_WINDOW:
        return None
    return states(closes)[-1]


def outcomes(closes: list[float], lows: list[float], i: int, state: RiskState) -> tuple[bool | None, bool | None]:
    """판정일 i 이후 20거래일의 (변동성 확대, 큰 낙폭) — 결과 창이 덜 찼으면 None."""
    if i + HORIZON >= len(closes):
        return None, None
    rets = [math.log(closes[j] / closes[j - 1]) for j in range(i + 1, i + HORIZON + 1)]
    mean = sum(rets) / HORIZON
    fut_rv = math.sqrt(sum((r - mean) ** 2 for r in rets) / (HORIZON - 1)) * ANNUAL
    fut_min = min(lows[i + 1:i + HORIZON + 1])
    return fut_rv > state.rv_q70, fut_min / closes[i] - 1 <= DROP_THRESHOLD
