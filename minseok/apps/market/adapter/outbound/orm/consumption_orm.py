from sqlalchemy import Float, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class ConsumptionOrm(MarketStatMixin, Base):
    __tablename__ = "consumption"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_consumption"),
        Index("ix_consumption_trdar_quarter", "trdar_code", "year_quarter"),
    )

    monthly_avg_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    income_range_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    food_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    clothing_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    household_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    medical_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    transport_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    leisure_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    culture_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    entertainment_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
