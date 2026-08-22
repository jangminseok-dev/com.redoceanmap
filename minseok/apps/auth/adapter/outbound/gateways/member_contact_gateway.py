from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.orm.user_orm import UserOrm
from hub.app.ports.output.member_contact_port import MemberContactPort


class MemberContactGateway(MemberContactPort):
    """허브의 MemberContactPort를 auth(스포크)가 구현한다.

    발송 목적 전용 조회 — 정지·탈퇴 회원과 이메일 없는 계정(일부 소셜)은 결과에서 뺀다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def emails_by_ids(self, user_ids: list[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (await self._session.execute(
            select(UserOrm.id, UserOrm.email).where(
                UserOrm.id.in_(user_ids),
                UserOrm.email.is_not(None),
                UserOrm.suspended_at.is_(None),
                UserOrm.deleted_at.is_(None),
            )
        )).all()
        return {user_id: email for user_id, email in rows}
