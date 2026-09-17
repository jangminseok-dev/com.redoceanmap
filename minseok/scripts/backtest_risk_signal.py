"""위험 신호 워크포워드 검증 — 변동성 확대·큰 낙폭 상태의 향후 20거래일 실측을 학습(~2020)/검증(2021~)으로 채점한다.

신호 보드(2026-09-17 재설계)는 이 리포트의 최신 1건에서 상태별 실측·검증 여부를 읽는다. 두 구간 모두 기준률과
95% 구간이 갈라진 신호만 수치를 보여 준다 — 검증 구간은 실행할수록 최신 데이터가 붙어 늘어나므로, 성질이 무너지면
다음 주 리포트에서 validated=False로 떨어지고 보드가 수치를 내린다(자동 강등, 자동 승격은 없다).

상태 판정·결과 채점은 실시간 보드와 같은 도메인 함수(risk_signal.states/outcomes)를 쓴다.

실행:
    python scripts/backtest_risk_signal.py            # 검증 + 리포트 INSERT
    python scripts/backtest_risk_signal.py --dry-run  # 요약 출력만

스케줄: k8s CronJob backtest-risk-signal(매주 토 06:00).
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, insert, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

from stock.adapter.outbound.orm.risk_signal_report_orm import RiskSignalReportOrm  # noqa: E402
from stock.domain.services import risk_signal  # noqa: E402
from stock.domain.services.risk_signal_backtester import RiskObservation, RiskSignalBacktester  # noqa: E402

TRAIN_END_YEAR = 2020
START = "2005-01-01"      # 2008 금융위기를 학습 구간에 넣는다

engine = create_engine(
    get_secret_manager().require("DATABASE_URL").replace("postgresql://", "postgresql+psycopg://")
)


def build() -> tuple[list[RiskObservation], dict]:
    bars = pd.read_sql(text(
        "SELECT ticker, ts::date AS d, low, close FROM price_bars"
        " WHERE timeframe = '1d' AND ts >= :start ORDER BY ticker, ts"
    ), engine, params={"start": START})
    observations: list[RiskObservation] = []
    tickers = 0
    for _ticker, g in bars.groupby("ticker"):
        closes, lows, dates = g.close.tolist(), g.low.tolist(), g.d.tolist()
        if len(closes) < risk_signal.MA_LONG + risk_signal.HORIZON + risk_signal.RANK_MIN:
            continue
        tickers += 1
        for i, state in enumerate(risk_signal.states(closes)):
            if state is None:
                continue
            vol_up, big_drop = risk_signal.outcomes(closes, lows, i, state)
            if vol_up is None:
                continue
            observations.append(RiskObservation(
                period="train" if dates[i].year <= TRAIN_END_YEAR else "test",
                vol_state=state.vol_state, drawdown_risk=state.drawdown_risk, vol_up=vol_up, big_drop=big_drop,
            ))
    meta = {"first_date": str(bars.d.min()), "last_date": str(bars.d.max()), "tickers": tickers}
    return observations, meta


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    observations, meta = build()
    payload = RiskSignalBacktester().aggregate(observations, train_end_year=TRAIN_END_YEAR, **meta)
    print(f"관측 {payload['n_observations']} · 종목 {meta['tickers']} · {meta['first_date']}~{meta['last_date']}")
    for s in payload["signals"]:
        for per in ("train", "test"):
            c = s[per]
            print(f"  {s['key']:10s} {per:5s} 발생 {c['rate']:.3f} [{c['lo']:.3f},{c['hi']:.3f}] n_eff={c['n_eff']:,.0f}"
                  f" · 기준 {c['base']:.3f} [{c['base_lo']:.3f},{c['base_hi']:.3f}] · {c['lift']:.2f}x")
        print(f"  → {s['label']}: {'검증됨' if s['validated'] else '검증 미달'}")
    if dry_run:
        print("--dry-run — INSERT 생략")
        return
    params = {"train_end_year": TRAIN_END_YEAR, "start": START, "horizon_days": risk_signal.HORIZON}
    with engine.begin() as conn:
        conn.execute(insert(RiskSignalReportOrm).values(params=params, payload=payload))
    print("risk_signal_reports에 리포트 1행 저장 완료")


if __name__ == "__main__":
    main()
