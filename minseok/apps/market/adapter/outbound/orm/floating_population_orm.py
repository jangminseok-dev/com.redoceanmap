from sqlalchemy import Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class FloatingPopulationOrm(MarketStatMixin, Base):
    __tablename__ = "floating_population"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_floating_population"),
        Index("ix_floating_population_trdar_quarter", "trdar_code", "year_quarter"),
    )

    total_floating_pop: Mapped[int] = mapped_column(Integer)
    male_floating_pop: Mapped[int] = mapped_column(Integer)
    female_floating_pop: Mapped[int] = mapped_column(Integer)
    age_10_floating_pop: Mapped[int] = mapped_column(Integer)
    age_20_floating_pop: Mapped[int] = mapped_column(Integer)
    age_30_floating_pop: Mapped[int] = mapped_column(Integer)
    age_40_floating_pop: Mapped[int] = mapped_column(Integer)
    age_50_floating_pop: Mapped[int] = mapped_column(Integer)
    age_60_plus_floating_pop: Mapped[int] = mapped_column(Integer)
    time_00_06_floating_pop: Mapped[int] = mapped_column(Integer)
    time_06_11_floating_pop: Mapped[int] = mapped_column(Integer)
    time_11_14_floating_pop: Mapped[int] = mapped_column(Integer)
    time_14_17_floating_pop: Mapped[int] = mapped_column(Integer)
    time_17_21_floating_pop: Mapped[int] = mapped_column(Integer)
    time_21_24_floating_pop: Mapped[int] = mapped_column(Integer)
    mon_floating_pop: Mapped[int] = mapped_column(Integer)
    tue_floating_pop: Mapped[int] = mapped_column(Integer)
    wed_floating_pop: Mapped[int] = mapped_column(Integer)
    thu_floating_pop: Mapped[int] = mapped_column(Integer)
    fri_floating_pop: Mapped[int] = mapped_column(Integer)
    sat_floating_pop: Mapped[int] = mapped_column(Integer)
    sun_floating_pop: Mapped[int] = mapped_column(Integer)
