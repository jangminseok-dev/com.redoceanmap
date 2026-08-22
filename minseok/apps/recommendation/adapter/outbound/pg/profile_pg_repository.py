from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation.adapter.outbound.orm.profile_orm import InvestorProfileOrm
from recommendation.app.ports.output.profile_repository import ProfileRepositoryPort
from recommendation.domain.entities.profile_entity import InvestorProfile


class ProfilePgRepository(ProfileRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, profile: InvestorProfile) -> InvestorProfile:
        values = dict(
            purpose=profile.purpose, risk_level=profile.risk_level,
            budget_band=profile.budget_band, debt_burden=profile.debt_burden,
            horizon=profile.horizon,
        )
        # 설문 재작성은 갱신 — 북마크(do_nothing)와 달리 전 필드를 덮어쓴다
        await self._session.execute(
            pg_insert(InvestorProfileOrm)
            .values(user_id=profile.user_id, **values)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={**values, "updated_at": func.now()},
            )
        )
        await self._session.commit()
        return await self.find_by_user(profile.user_id)

    async def find_by_user(self, user_id: int) -> InvestorProfile | None:
        row = (await self._session.execute(
            select(InvestorProfileOrm).where(InvestorProfileOrm.user_id == user_id)
        )).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def delete(self, user_id: int) -> bool:
        result = await self._session.execute(
            delete(InvestorProfileOrm).where(InvestorProfileOrm.user_id == user_id)
        )
        await self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(r: InvestorProfileOrm) -> InvestorProfile:
        return InvestorProfile(
            id=r.id, user_id=r.user_id, purpose=r.purpose, risk_level=r.risk_level,
            budget_band=r.budget_band, debt_burden=r.debt_burden, horizon=r.horizon,
            updated_at=r.updated_at,
        )
