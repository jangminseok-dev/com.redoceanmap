from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.news_alert_dto import AlertableNews
from hub.app.ports.output.news_alert_feed_port import NewsAlertFeedPort
from stock.adapter.outbound.orm.news_alert_cursor_orm import NewsAlertCursorOrm
from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.adapter.outbound.pg.news_pg_repository import DEFAULT_LABELER

_CURSOR_ID = 1


class NewsAlertFeedGateway(NewsAlertFeedPort):
    """허브의 NewsAlertFeedPort를 stock(스포크)이 구현한다.

    커서(워터마크)의 소유자: 첫 호출은 현재 최신 라벨을 커서로 삼고 빈 목록을 준다
    (과거 백로그 홍수 방지 — 포트 계약). 이후 호출은 커서 뒤 강한 감성 라벨을 내주고
    커서를 전진시킨다. 라벨은 기본 라벨러(DEFAULT_LABELER)만 본다 — 재라벨 실험 행이
    같은 뉴스를 다시 알림으로 만들지 않게.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pull_alertable(
        self, min_abs_sentiment: float, limit: int = 200
    ) -> list[AlertableNews]:
        max_id = (await self._session.execute(
            select(func.coalesce(func.max(NewsLabelOrm.id), 0))
        )).scalar_one()

        cursor = (await self._session.execute(
            select(NewsAlertCursorOrm.last_label_id)
            .where(NewsAlertCursorOrm.id == _CURSOR_ID)
        )).scalar_one_or_none()
        if cursor is None:
            # 부트스트랩 — 지금까지의 라벨은 알림 대상이 아니다(백로그 홍수 방지)
            self._session.add(NewsAlertCursorOrm(id=_CURSOR_ID, last_label_id=max_id))
            await self._session.commit()
            return []

        rows = (await self._session.execute(
            select(
                NewsLabelOrm.id,
                NewsArticleOrm.id,
                NewsArticleOrm.ticker,
                NewsArticleOrm.title,
                NewsLabelOrm.sentiment,
                NewsLabelOrm.event_type,
                NewsArticleOrm.published_at,
            )
            .join(NewsArticleOrm, NewsArticleOrm.id == NewsLabelOrm.news_id)
            .where(
                NewsLabelOrm.id > cursor,
                NewsLabelOrm.labeler == DEFAULT_LABELER,
                func.abs(NewsLabelOrm.sentiment) >= min_abs_sentiment,
                NewsArticleOrm.ticker != "",  # 종목 무관 기사는 알림 축이 없다
            )
            .order_by(NewsLabelOrm.id.asc())
            .limit(limit)
        )).all()

        # limit에 걸렸으면 마지막으로 내준 라벨까지만 전진(나머지는 다음 스캔),
        # 다 내줬으면 전체 최신까지 전진(필터에 안 걸린 라벨을 재훑지 않는다)
        new_cursor = rows[-1][0] if len(rows) == limit else max_id
        if new_cursor != cursor:
            await self._session.execute(
                update(NewsAlertCursorOrm)
                .where(NewsAlertCursorOrm.id == _CURSOR_ID)
                .values(last_label_id=new_cursor)
            )
            await self._session.commit()

        return [
            AlertableNews(
                news_id=news_id, ticker=ticker, title=title,
                sentiment=sentiment, event_type=event_type, published_at=published_at,
            )
            for _, news_id, ticker, title, sentiment, event_type, published_at in rows
        ]
