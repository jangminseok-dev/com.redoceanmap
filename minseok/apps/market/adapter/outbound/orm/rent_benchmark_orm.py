from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RentBenchmarkOrm(Base):
    """한국부동산원 R-ONE 상가 임대동향 — 서울 상권·권역·시 단위 임대료(원/㎡·월)와 공실률(%).

    R-ONE 상권은 서울에 59곳뿐이라 우리 trade_area 1,650곳 대부분은 권역(level 1) 평균으로
    폴백한다(rent_matcher). 적재는 scripts/collect_rone_rent.py — (building_type, year_quarter, cls_id) upsert.
    """

    __tablename__ = "rent_benchmarks"
    __table_args__ = (
        UniqueConstraint("building_type", "year_quarter", "cls_id", name="uq_rent_benchmarks_type_quarter_cls"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    building_type: Mapped[str] = mapped_column(String(16))  # small | medium_large | aggregate
    year_quarter: Mapped[int] = mapped_column(Integer, index=True)  # 20243 형식
    cls_id: Mapped[str] = mapped_column(String(16))  # R-ONE CLS_ID
    cls_fullnm: Mapped[str] = mapped_column(String(80))  # "서울>기타>혜화동"
    level: Mapped[int] = mapped_column(Integer)  # 0 시 · 1 권역 · 2 상권
    region_name: Mapped[str] = mapped_column(String(40), index=True)  # 마지막 계층명
    rent_per_sqm_krw: Mapped[int] = mapped_column(Integer)
    vacancy_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 임대동향 수익률(분기 %) — 소득(임대료)·자본(자산가치 변동)·투자(=합) — 2024Q3~ 빈티지
    income_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    investment_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
