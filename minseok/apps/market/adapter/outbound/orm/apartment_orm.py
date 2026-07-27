from sqlalchemy import BigInteger, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class ApartmentOrm(MarketStatMixin, Base):
    __tablename__ = "apartment"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_apartment"),
        Index("ix_apartment_trdar_quarter", "trdar_code", "year_quarter"),
    )

    complex_count: Mapped[int] = mapped_column(Integer)
    area_under_66_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_66_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_99_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_132_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_165_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_under_1b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_1b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_2b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_3b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_4b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_5b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_over_6b_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_area: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[int] = mapped_column(BigInteger)
