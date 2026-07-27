from sqlalchemy import Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class ResidentPopulationOrm(MarketStatMixin, Base):
    __tablename__ = "resident_population"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_resident_population"),
        Index("ix_resident_population_trdar_quarter", "trdar_code", "year_quarter"),
    )

    total_resident_pop: Mapped[int] = mapped_column(Integer)
    male_resident_pop: Mapped[int] = mapped_column(Integer)
    female_resident_pop: Mapped[int] = mapped_column(Integer)
    age_10_resident_pop: Mapped[int] = mapped_column(Integer)
    age_20_resident_pop: Mapped[int] = mapped_column(Integer)
    age_30_resident_pop: Mapped[int] = mapped_column(Integer)
    age_40_resident_pop: Mapped[int] = mapped_column(Integer)
    age_50_resident_pop: Mapped[int] = mapped_column(Integer)
    age_60_plus_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_10_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_20_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_30_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_40_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_50_resident_pop: Mapped[int] = mapped_column(Integer)
    male_age_60_plus_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_10_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_20_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_30_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_40_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_50_resident_pop: Mapped[int] = mapped_column(Integer)
    female_age_60_plus_resident_pop: Mapped[int] = mapped_column(Integer)
    total_household_count: Mapped[int] = mapped_column(Integer)
    apartment_household_count: Mapped[int] = mapped_column(Integer)
    non_apartment_household_count: Mapped[int] = mapped_column(Integer)
