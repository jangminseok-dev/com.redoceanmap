from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class StoreOrm(MarketStatMixin, Base):
    __tablename__ = "store"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", "service_code", name="uq_store"),
        Index("ix_store_trdar_quarter", "trdar_code", "year_quarter"),
    )

    service_code: Mapped[str] = mapped_column(ForeignKey("service_category.code"), index=True)
    store_count: Mapped[int] = mapped_column(Integer)
    similar_industry_store_count: Mapped[int] = mapped_column(Integer)
    opening_rate: Mapped[int] = mapped_column(Integer)
    opening_store_count: Mapped[int] = mapped_column(Integer)
    closure_rate: Mapped[int] = mapped_column(Integer)
    closure_store_count: Mapped[int] = mapped_column(Integer)
    franchise_store_count: Mapped[int] = mapped_column(Integer)
