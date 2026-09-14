from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.trade_area_division_orm import TradeAreaDivisionOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.dtos.area_public_dto import AreaIndexRow
from market.app.ports.output.area_index_repository import AreaIndexRepositoryPort


class AreaIndexPgRepository(AreaIndexRepositoryPort):
    """상권 차원 목록 — trade_area + 상권구분 + 행정동→자치구. 좌표·면적은 읽지 않는다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _stmt(self):
        dong = aliased(RegionOrm)  # 행정동(level2)
        gu = aliased(RegionOrm)    # 자치구(level1)
        return (
            select(TradeAreaOrm.code, TradeAreaOrm.name, gu.name, TradeAreaDivisionOrm.name)
            .join(TradeAreaDivisionOrm, TradeAreaOrm.division_code == TradeAreaDivisionOrm.code)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
        )

    async def find_one(self, trdar_code: int) -> AreaIndexRow | None:
        row = (await self._session.execute(
            self._stmt().where(TradeAreaOrm.code == trdar_code)
        )).first()
        return _row(row) if row else None

    async def list_all(self) -> list[AreaIndexRow]:
        rows = (await self._session.execute(self._stmt().order_by(TradeAreaOrm.code))).all()
        return [_row(r) for r in rows]


def _row(row) -> AreaIndexRow:
    code, name, gu_name, division_name = row
    return AreaIndexRow(trdar_code=code, trdar_name=name, district_name=gu_name or "",
                        division_name=division_name)
