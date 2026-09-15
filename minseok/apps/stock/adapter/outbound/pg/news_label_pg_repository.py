from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.app.dtos.news_label_dto import UnlabeledNews
from stock.app.ports.output.news_label_repository import NewsLabelRepositoryPort
from stock.domain.entities.news_label import NewsLabel


class NewsLabelPgRepository(NewsLabelRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, labels: list[NewsLabel]) -> int:
        if not labels:
            return 0
        stmt = (
            pg_insert(NewsLabelOrm)
            .values([
                {
                    "news_id": l.news_id,
                    "labeler": l.labeler,
                    "sentiment": l.sentiment,
                    "event_type": l.event_type,
                    "confidence": l.confidence,
                }
                for l in labels
            ])
            .on_conflict_do_nothing(index_elements=["news_id", "labeler"])
            .returning(NewsLabelOrm.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return len(result.scalars().all())

    async def unlabeled(self, labeler: str, limit: int) -> list[UnlabeledNews]:
        exists_label = (
            select(NewsLabelOrm.id)
            .where(NewsLabelOrm.news_id == NewsArticleOrm.id, NewsLabelOrm.labeler == labeler)
            .exists()
        )
        stmt = (
            select(NewsArticleOrm.id, NewsArticleOrm.ticker, NewsArticleOrm.title)
            .where(~exists_label)
            # 최신 기사부터 — 모델 교체로 전량이 미라벨이 되면(2026-09-15 EXAONE→Gemma 10.5만 건)
            # 소비처(RAG·피드·알림)가 먼저 보는 최근 기사를 먼저 채운다. 평시에도 신규 기사가 먼저다.
            .order_by(NewsArticleOrm.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            UnlabeledNews(news_id=news_id, ticker=ticker, title=title)
            for news_id, ticker, title in result.all()
        ]
