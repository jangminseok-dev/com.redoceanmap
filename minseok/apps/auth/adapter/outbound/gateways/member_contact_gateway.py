from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.orm.user_orm import UserOrm
from auth.domain.value_objects.deliverable_email import is_deliverable
from hub.app.ports.output.member_contact_port import MemberContactPort


class MemberContactGateway(MemberContactPort):
    """허브의 MemberContactPort를 auth(스포크)가 구현한다.

    발송 목적 전용 조회 — 정지·탈퇴 회원과 이메일 없는 계정(일부 소셜)은 결과에서 뺀다.
    받을 수 없는 주소(QA 계정의 자체 도메인·예약 도메인)도 뺀다 — 반송 안내가 발신 계정 받은편지함을 채웠다(2026-09-21).
    **이메일을 인증한 회원만** 남긴다 — 아무 주소로나 가입해 북마크하면 그 주소로 매시간 메일이 나가던 구조를 막는다.
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
                UserOrm.email_verified_at.is_not(None),  # 인증된 주소만 — 남의 주소·오타 주소로 알림이 나가지 않게
            )
        )).all()
        return {user_id: email for user_id, email in rows if is_deliverable(email)}
