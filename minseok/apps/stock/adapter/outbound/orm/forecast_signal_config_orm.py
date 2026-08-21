from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ForecastSignalConfigOrm(Base):
    """forecast·스냅샷 슬라이스의 활성 판정 조합 — 재적합 승격 이력이 행으로 쌓인다.

    활성은 항상 정확히 1행(부분 유니크 인덱스, alembic `h5e6f7a8b9c0`). 승격은
    기존 활성 해제 + 신규 행 활성 전환 한 트랜잭션. 파라미터는 손잡이 스키마가
    고정돼 있어 JSONB가 아니라 컬럼 전개다.
    """

    __tablename__ = "forecast_signal_configs"
    __table_args__ = (
        Index(
            "uq_forecast_signal_configs_active", "is_active",
            unique=True, postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_key: Mapped[str] = mapped_column(String(24), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    up_threshold: Mapped[float] = mapped_column(Float)
    down_threshold: Mapped[float] = mapped_column(Float)
    w_sentiment: Mapped[float] = mapped_column(Float)
    w_rsi: Mapped[float] = mapped_column(Float)
    w_trend: Mapped[float] = mapped_column(Float)
    w_bb: Mapped[float] = mapped_column(Float)
    w_obv: Mapped[float] = mapped_column(Float)
    w_momentum: Mapped[float] = mapped_column(Float)
    atr_veto: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_confirm: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8))  # seed | refit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
