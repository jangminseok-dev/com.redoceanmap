from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RiskSignalReportOrm(Base):
    """위험 신호 검증 리포트 — 주간 백테스트 실행당 1행(2026-09-17 신호 보드 재설계).

    쓰기는 scripts/backtest_risk_signal.py(k8s CronJob), 조회는 신호 보드(최신 1건 — 상태별 실측·검증 여부).
    payload 스키마의 단일 정의처는 `stock/domain/services/risk_signal_backtester.py`.
    """

    __tablename__ = "risk_signal_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    params: Mapped[dict] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB)
