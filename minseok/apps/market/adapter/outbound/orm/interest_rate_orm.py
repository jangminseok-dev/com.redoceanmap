from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InterestRateOrm(Base):
    """한국은행 ECOS 금리 — 기준금리(722Y001)·예금은행 대출금리(121Y006), 월 단위(연 %).

    전국 값이라 상권 매칭이 없다. 유일 소비처가 market 재무 엔진이라 market 전용 DB에 둔다.
    적재는 scripts/collect_ecos_rates.py — (stat_code, item_name, year_month) upsert.
    """

    __tablename__ = "interest_rates"
    __table_args__ = (
        UniqueConstraint("stat_code", "item_name", "year_month", name="uq_interest_rates_stat_item_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stat_code: Mapped[str] = mapped_column(String(16))
    item_name: Mapped[str] = mapped_column(String(60))  # "한국은행 기준금리" · "대출평균" · "기업대출"
    year_month: Mapped[int] = mapped_column(Integer, index=True)  # 202508
    rate: Mapped[float] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
