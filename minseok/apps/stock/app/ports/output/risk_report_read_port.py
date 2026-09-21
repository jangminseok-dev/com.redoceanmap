from __future__ import annotations

from abc import ABC
from datetime import datetime


class RiskReportReadPort(ABC):
    """위험 신호 검증 리포트 조회 — 보드와 종목 예측이 같은 최신 리포트를 읽는다.

    쓰기는 scripts/backtest_risk_signal.py(k8s CronJob)가 DB에 직접 한다. payload 스키마의 단일 정의처는
    `stock/domain/services/risk_signal_backtester.py`.
    """

    async def find_latest_risk_report(self) -> tuple[datetime, dict] | None:
        """최신 1건(실행 시각, payload). 없으면 None — 구현 전 저장소는 기본값."""
        return None
