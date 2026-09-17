"""위험 신호 검증 집계 — 상태별 결과 발생률을 학습/검증 구간으로 나눠 기준률과 대조한다(순수 도메인).

payload 스키마의 단일 정의처. 겹침 보정: 20거래일 결과 창이 날마다 겹치므로 유효 표본 = 관측 수 ÷ 20
(`backtest_report.overlap_effective`와 같은 원칙). 신호가 "검증됨"이려면 **학습·검증 두 구간 모두**
95% Wilson 구간이 기준률 구간과 갈라져야 한다 — 한 구간에서만 갈리면 보드는 수치를 쓰지 않는다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from stock.domain.services.risk_signal import HORIZON


@dataclass(frozen=True)
class RiskObservation:
    period: str            # train | test
    vol_state: str
    drawdown_risk: str
    vol_up: bool
    big_drop: bool


# (키, 표시명, 결과, 조건 필드, 조건 값, 방향 — 기준보다 높아야 high / 낮아야 low)
SIGNALS = (
    ("vol_high", "변동성 확대 가능성 높음", "vol_up", "vol_state", "HIGH", "high"),
    ("vol_low", "변동성 확대 가능성 낮음", "vol_up", "vol_state", "LOW", "low"),
    ("drop_high", "큰 낙폭 위험 높음", "big_drop", "drawdown_risk", "HIGH", "high"),
    ("drop_low", "큰 낙폭 위험 낮음", "big_drop", "drawdown_risk", "LOW", "low"),
)
OUTCOME_LABELS = {
    "vol_up": "20거래일 안에 변동성이 평소(자기 1년 70분위)보다 커짐",
    "big_drop": "20거래일 안에 한 번이라도 -10% 이상 하락",
}


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return ctr - half, ctr + half


def _cell(obs: list[RiskObservation], outcome: str, field: str, value: str) -> dict:
    hits_all = sum(getattr(o, outcome) for o in obs)
    subset = [o for o in obs if getattr(o, field) == value]
    hits = sum(getattr(o, outcome) for o in subset)
    n_eff, k_eff = len(subset) / HORIZON, hits / HORIZON
    lo, hi = wilson(k_eff, n_eff)
    base_lo, base_hi = wilson(hits_all / HORIZON, len(obs) / HORIZON)
    rate = hits / len(subset) if subset else None
    base = hits_all / len(obs) if obs else None
    return {
        "rate": rate, "lo": lo, "hi": hi, "n": len(subset), "n_eff": round(n_eff, 1),
        "base": base, "base_lo": base_lo, "base_hi": base_hi,
        "lift": rate / base if rate is not None and base else None,
        "share": len(subset) / len(obs) if obs else None,
    }


def _separated(cell: dict, side: str) -> bool:
    if cell["lo"] is None or cell["base_lo"] is None:
        return False
    return cell["lo"] > cell["base_hi"] if side == "high" else cell["hi"] < cell["base_lo"]


class RiskSignalBacktester:
    def aggregate(self, observations: list[RiskObservation], *, train_end_year: int, first_date: str, last_date: str,
                  tickers: int) -> dict:
        by_period = {p: [o for o in observations if o.period == p] for p in ("train", "test")}
        signals = []
        for key, label, outcome, field, value, side in SIGNALS:
            train = _cell(by_period["train"], outcome, field, value)
            test = _cell(by_period["test"], outcome, field, value)
            signals.append({
                "key": key, "label": label, "outcome": outcome, "outcome_label": OUTCOME_LABELS[outcome],
                "side": side, "train": train, "test": test,
                "validated": _separated(train, side) and _separated(test, side),
            })
        return {
            "horizon_days": HORIZON, "train_end_year": train_end_year, "first_date": first_date,
            "last_date": last_date, "tickers": tickers,
            "n_observations": {p: len(v) for p, v in by_period.items()},
            "signals": signals,
        }
