from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.franchise_cost_dto import FranchiseCostItem
from hub.app.ports.output.franchise_cost_storage_port import FranchiseCostStoragePort
from market.adapter.outbound.orm.franchise_industry_cost_orm import FranchiseIndustryCostOrm


class FranchiseCostStorageGateway(FranchiseCostStoragePort):
    """허브 FranchiseCostStoragePort를 market이 구현 — (year, sector, industry_name) upsert."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, items: list[FranchiseCostItem]) -> int:
        if not items:
            return 0
        rows = [dict(year=i.year, sector=i.sector, industry_name=i.industry_name, franchise_fee=i.franchise_fee,
                     education_fee=i.education_fee, deposit=i.deposit, other_fee=i.other_fee,
                     total_amount=i.total_amount, brand_count=i.brand_count, raw=i.raw) for i in items]
        stmt = insert(FranchiseIndustryCostOrm).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_franchise_industry_costs_year_sector_industry",
            set_={c: getattr(stmt.excluded, c) for c in ("franchise_fee", "education_fee", "deposit", "other_fee",
                                                          "total_amount", "brand_count", "raw")},
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return len(rows)  # 대량 upsert는 드라이버가 rowcount(-1)를 안 준다 — 보낸 건수를 반영 건수로
