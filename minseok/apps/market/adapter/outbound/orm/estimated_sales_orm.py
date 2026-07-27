from sqlalchemy import BigInteger, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class EstimatedSalesOrm(MarketStatMixin, Base):
    __tablename__ = "estimated_sales"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", "service_code", name="uq_estimated_sales"),
        Index("ix_estimated_sales_trdar_quarter", "trdar_code", "year_quarter"),
    )

    service_code: Mapped[str] = mapped_column(ForeignKey("service_category.code"), index=True)

    monthly_sales_amount: Mapped[int] = mapped_column(BigInteger)
    monthly_sales_count: Mapped[int] = mapped_column(Integer)
    weekday_sales_amount: Mapped[int] = mapped_column(BigInteger)
    weekend_sales_amount: Mapped[int] = mapped_column(BigInteger)
    mon_sales_amount: Mapped[int] = mapped_column(BigInteger)
    tue_sales_amount: Mapped[int] = mapped_column(BigInteger)
    wed_sales_amount: Mapped[int] = mapped_column(BigInteger)
    thu_sales_amount: Mapped[int] = mapped_column(BigInteger)
    fri_sales_amount: Mapped[int] = mapped_column(BigInteger)
    sat_sales_amount: Mapped[int] = mapped_column(BigInteger)
    sun_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_00_06_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_06_11_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_11_14_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_14_17_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_17_21_sales_amount: Mapped[int] = mapped_column(BigInteger)
    time_21_24_sales_amount: Mapped[int] = mapped_column(BigInteger)
    male_sales_amount: Mapped[int] = mapped_column(BigInteger)
    female_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_10_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_20_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_30_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_40_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_50_sales_amount: Mapped[int] = mapped_column(BigInteger)
    age_60_plus_sales_amount: Mapped[int] = mapped_column(BigInteger)
    weekday_sales_count: Mapped[int] = mapped_column(Integer)
    weekend_sales_count: Mapped[int] = mapped_column(Integer)
    mon_sales_count: Mapped[int] = mapped_column(Integer)
    tue_sales_count: Mapped[int] = mapped_column(Integer)
    wed_sales_count: Mapped[int] = mapped_column(Integer)
    thu_sales_count: Mapped[int] = mapped_column(Integer)
    fri_sales_count: Mapped[int] = mapped_column(Integer)
    sat_sales_count: Mapped[int] = mapped_column(Integer)
    sun_sales_count: Mapped[int] = mapped_column(Integer)
    time_00_06_sales_count: Mapped[int] = mapped_column(Integer)
    time_06_11_sales_count: Mapped[int] = mapped_column(Integer)
    time_11_14_sales_count: Mapped[int] = mapped_column(Integer)
    time_14_17_sales_count: Mapped[int] = mapped_column(Integer)
    time_17_21_sales_count: Mapped[int] = mapped_column(Integer)
    time_21_24_sales_count: Mapped[int] = mapped_column(Integer)
    male_sales_count: Mapped[int] = mapped_column(Integer)
    female_sales_count: Mapped[int] = mapped_column(Integer)
    age_10_sales_count: Mapped[int] = mapped_column(Integer)
    age_20_sales_count: Mapped[int] = mapped_column(Integer)
    age_30_sales_count: Mapped[int] = mapped_column(Integer)
    age_40_sales_count: Mapped[int] = mapped_column(Integer)
    age_50_sales_count: Mapped[int] = mapped_column(Integer)
    age_60_plus_sales_count: Mapped[int] = mapped_column(Integer)
