from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class KeyMoneyBenchmarkOrm(Base):
    """한국부동산원 R-ONE 시도별/업종별 상가권리금(연간) — 서울 × 업종 대분류(표준산업분류 대분류 5 + 전체).

    권리금 수준은 **권리금이 있는 점포** 기준 통계다(유 비율은 따로). 적재는 scripts/collect_rone_rent.py —
    (year, region_name, industry_group) upsert. 원본 만원 → 원.
    """

    __tablename__ = "key_money_benchmarks"
    __table_args__ = (
        UniqueConstraint("year", "region_name", "industry_group", name="uq_key_money_year_region_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    region_name: Mapped[str] = mapped_column(String(20))       # "서울"
    industry_group: Mapped[str] = mapped_column(String(60))    # "숙박 및 음식점업" · "전체"
    key_money_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)   # 권리금 유 비율(%)
    avg_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    median_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    per_sqm_avg_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
