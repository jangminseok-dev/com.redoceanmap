from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PaperEquityDailyOrm(Base):
    """일별 평가 — 자산 곡선의 점. 배치가 하루 한 번 쓴다."""

    __tablename__ = "paper_equity_daily"
    __table_args__ = (
        UniqueConstraint("account_id", "as_of", name="uq_paper_equity_daily_account_as_of"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    as_of: Mapped[date] = mapped_column(Date)
    cash_krw: Mapped[float] = mapped_column(Float)
    positions_value_krw: Mapped[float] = mapped_column(Float)
    equity_krw: Mapped[float] = mapped_column(Float)
    replayed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
