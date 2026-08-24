from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.bookmark_directory_dto import BookmarkedArea, BookmarkedStock
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from recommendation.adapter.outbound.orm.alert_orm import AlertSettingOrm
from recommendation.adapter.outbound.orm.bookmark_orm import BookmarkOrm


class BookmarkDirectoryGateway(BookmarkDirectoryPort):
    """허브의 BookmarkDirectoryPort를 recommendation(스포크)이 구현한다.

    전 사용자 횡단 조회 전용 — RecommendationDirectoryGateway와 같은 직접 조회 선례.
    알림 수신을 끈 회원(user_alert_settings.email_alerts=false)은 여기서 제외한다 —
    발송 대상 열람이라는 계약 의미에 속한다(MemberContactPort가 정지·탈퇴를 빼는 것과
    같은 논리). 행이 없는 회원은 기본 수신(포함)이다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def stock_bookmarks(self) -> list[BookmarkedStock]:
        rows = (await self._session.execute(
            select(BookmarkOrm.user_id, BookmarkOrm.target_key, BookmarkOrm.label)
            .outerjoin(AlertSettingOrm, AlertSettingOrm.user_id == BookmarkOrm.user_id)
            .where(
                BookmarkOrm.target_type == "stock",
                # 설정 행이 없으면(NULL) 기본 수신 — false 명시자만 제외
                AlertSettingOrm.email_alerts.isnot(False),
            )
            .order_by(BookmarkOrm.user_id, BookmarkOrm.target_key)
        )).all()
        return [
            BookmarkedStock(user_id=user_id, ticker=target_key, label=label)
            for user_id, target_key, label in rows
        ]

    async def area_bookmarks(self) -> list[BookmarkedArea]:
        rows = (await self._session.execute(
            select(BookmarkOrm.user_id, BookmarkOrm.target_key, BookmarkOrm.label)
            .outerjoin(AlertSettingOrm, AlertSettingOrm.user_id == BookmarkOrm.user_id)
            .where(
                BookmarkOrm.target_type == "area",
                # 설정 행이 없으면(NULL) 기본 수신 — false 명시자만 제외
                AlertSettingOrm.email_alerts.isnot(False),
            )
            .order_by(BookmarkOrm.user_id, BookmarkOrm.target_key)
        )).all()
        # target_key는 상권 코드 문자열 — 숫자가 아닌 잔존 데이터는 알림 축이 될 수 없어 거른다
        return [
            BookmarkedArea(user_id=user_id, trdar_code=int(target_key), label=label)
            for user_id, target_key, label in rows
            if target_key.isdigit()
        ]

    async def telegram_chat_ids(self, user_ids: list[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (await self._session.execute(
            select(AlertSettingOrm.user_id, AlertSettingOrm.telegram_chat_id)
            .where(
                AlertSettingOrm.user_id.in_(user_ids),
                AlertSettingOrm.telegram_chat_id.is_not(None),
            )
        )).all()
        return {user_id: chat_id for user_id, chat_id in rows if chat_id}
