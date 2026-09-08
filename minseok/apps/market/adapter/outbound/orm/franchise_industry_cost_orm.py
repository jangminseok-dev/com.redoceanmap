from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FranchiseIndustryCostOrm(Base):
    """공정위 가맹정보 업종별 창업비용(정보공개서 평균, 원). 상권 축의 비용 공백을 메우는 첫 팩트.

    가맹금·교육비·보증금·기타의 합계라 점포 임대료·인테리어는 없다 — 읽는 쪽이 한계를 함께 말한다.
    적재는 scripts/collect_franchise_costs.py — (year, sector, industry_name) 교체 멱등.
    """

    __tablename__ = "franchise_industry_costs"
    __table_args__ = (
        UniqueConstraint("year", "sector", "industry_name", name="uq_franchise_industry_costs_year_sector_industry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    sector: Mapped[str] = mapped_column(String(8))  # 외식 | 도소매 | 서비스
    industry_name: Mapped[str] = mapped_column(String(60))
    franchise_fee: Mapped[int] = mapped_column(BigInteger)
    education_fee: Mapped[int] = mapped_column(BigInteger)
    deposit: Mapped[int] = mapped_column(BigInteger)
    other_fee: Mapped[int] = mapped_column(BigInteger)
    total_amount: Mapped[int] = mapped_column(BigInteger)
    brand_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
