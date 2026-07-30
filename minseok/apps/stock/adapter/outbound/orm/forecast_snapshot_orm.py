from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ForecastSnapshotOrm(Base):
    __tablename__ = "forecast_snapshots"
    __table_args__ = (
        # 티커·horizon별 봉 하나당 스냅샷 하나 — 주말/재실행은 ON CONFLICT로 자연 스킵
        UniqueConstraint(
            "ticker", "horizon_days", "as_of",
            name="uq_forecast_snapshots_ticker_horizon_as_of",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_days: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(8))  # UP | DOWN | NEUTRAL
    base_price: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    signals: Mapped[list] = mapped_column(JSONB)  # [{key, signal, weight, contribution} × 6]
    up_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_up_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ready: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    band_source: Mapped[str | None] = mapped_column(String(10), nullable=True)  # quantile | atr
    q25_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    q75_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # --- 판정 재현·재적합용 (alembic a1b2c3d4e5f7) ---
    # NULL = 2026-07-30 이전 default() 조합(전량 NEUTRAL 구간) — 이력 구분용
    signal_config: Mapped[str | None] = mapped_column(String(24), nullable=True)
    rsi: Mapped[float | None] = mapped_column(Float, nullable=True)
    bb_percent_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_12_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drawdown_from_high_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    above_support_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trough_median_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trough_q25_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_days_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    realized_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_trough_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime: Mapped[str | None] = mapped_column(String(10), nullable=True)  # BULL | BEAR | HIGH_VOL
    regime_conditional: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    earnings_veto: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
