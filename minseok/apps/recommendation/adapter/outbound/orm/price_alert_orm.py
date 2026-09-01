from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PriceAlertOrm(Base):
    """사용자가 직접 건 가격 도달 조건(손절·익절선 — 시그널 대개편 [6]).

    도달 시 1회 통지 후 active=false(one-shot). `user_alert_deliveries`를 dedupe로
    재사용하지 않는다 — 그 테이블은 북마크 스캔이 매 실행 전체 교체(delete-all)하므로
    다른 스캔이 섞이면 서로의 상태를 지운다. 재알림은 사용자가 조건을 다시 등록하는 것.
    """

    __tablename__ = "user_price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    ticker: Mapped[str] = mapped_column(String(30))
    target_price: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(5))  # above | below
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
