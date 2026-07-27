from sqlalchemy import Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class WorkingPopulationOrm(MarketStatMixin, Base):
    __tablename__ = "working_population"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_working_population"),
        Index("ix_working_population_trdar_quarter", "trdar_code", "year_quarter"),
    )

    total_working_pop: Mapped[int] = mapped_column(Integer)
    male_working_pop: Mapped[int] = mapped_column(Integer)
    female_working_pop: Mapped[int] = mapped_column(Integer)
    age_10_working_pop: Mapped[int] = mapped_column(Integer)
    age_20_working_pop: Mapped[int] = mapped_column(Integer)
    age_30_working_pop: Mapped[int] = mapped_column(Integer)
    age_40_working_pop: Mapped[int] = mapped_column(Integer)
    age_50_working_pop: Mapped[int] = mapped_column(Integer)
    age_60_plus_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_10_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_20_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_30_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_40_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_50_working_pop: Mapped[int] = mapped_column(Integer)
    male_age_60_plus_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_10_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_20_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_30_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_40_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_50_working_pop: Mapped[int] = mapped_column(Integer)
    female_age_60_plus_working_pop: Mapped[int] = mapped_column(Integer)
