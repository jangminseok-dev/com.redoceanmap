from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_errors import is_infra_failure
from market.adapter.outbound.orm.market_news_article_orm import MarketNewsArticleOrm
from market.app.dtos.market_news_search_dto import MarketNewsSearchRow
from market.app.ports.output.market_news_repository import MarketNewsRepositoryPort
from market.domain.entities.market_news_article import MarketNewsArticle
from market.domain.services.rrf_fusion import rrf_merge

logger = logging.getLogger(__name__)

# 하이브리드 검색(R2) — 채널별 후보 폭. 라벨 확정 후 파라미터 스윕(R2 ③)의 조정 대상.
HYBRID_CHANNEL_LIMIT = 30


class MarketNewsPgRepository(MarketNewsRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, articles: list[MarketNewsArticle]) -> int:
        """일괄 저장. 한 행이 거부돼도 배치 전체를 잃지 않도록 행 단위로 되짚는다."""
        if not articles:
            return 0
        try:
            return await self._insert(articles)
        except DBAPIError as e:
            if is_infra_failure(e):
                raise  # 행 문제가 아니다 — 되짚으면 전 행이 조용히 유실된다(배치가 재시도하게)
            await self._session.rollback()
            return await self._insert_row_by_row(articles)

    async def _insert(self, articles: list[MarketNewsArticle]) -> int:
        stmt = (
            pg_insert(MarketNewsArticleOrm)
            .values([
                {
                    "title": a.title,
                    "source": a.source,
                    "url": a.url,
                    "area_tag": a.area_tag,
                    "published_at": a.published_at,
                }
                for a in articles
            ])
            .on_conflict_do_nothing(index_elements=["url", "area_tag"])
            .returning(MarketNewsArticleOrm.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return len(result.scalars().all())

    async def _insert_row_by_row(self, articles: list[MarketNewsArticle]) -> int:
        saved = 0
        for a in articles:
            try:
                saved += await self._insert([a])
            except DBAPIError as e:
                if is_infra_failure(e):
                    raise  # 인프라 장애 — 남은 행도 전부 같은 이유로 실패한다
                await self._session.rollback()
                logger.warning(
                    "[market-news] 행 거부 — 건너뜀 (area_tag=%s, url %d자): %s",
                    a.area_tag, len(a.url), e.orig,
                )
        return saved

    async def unembedded(self, limit: int) -> list[tuple[int, str]]:
        stmt = (
            select(MarketNewsArticleOrm.id, MarketNewsArticleOrm.title)
            .where(MarketNewsArticleOrm.embedding.is_(None))
            .order_by(MarketNewsArticleOrm.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row_id, title) for row_id, title in result.all()]

    async def set_embeddings(self, items: list[tuple[int, list[float]]]) -> int:
        if not items:
            return 0
        for row_id, embedding in items:
            await self._session.execute(
                update(MarketNewsArticleOrm)
                .where(MarketNewsArticleOrm.id == row_id)
                .values(embedding=embedding)
            )
        await self._session.commit()
        return len(items)

    async def search_similar(
        self, embedding: list[float], limit: int = 4
    ) -> list[MarketNewsSearchRow]:
        stmt = (
            select(MarketNewsArticleOrm)
            .where(MarketNewsArticleOrm.embedding.is_not(None))
            .order_by(MarketNewsArticleOrm.embedding.cosine_distance(embedding))
            .limit(limit * 2)  # (url, area_tag) 유니크 구조상 다행 존재 — 여유 조회 후 제목 dedupe
        )
        result = await self._session.execute(stmt)
        rows: list[MarketNewsSearchRow] = []
        seen_titles: set[str] = set()
        for orm in result.scalars().all():
            if orm.title in seen_titles:
                continue
            seen_titles.add(orm.title)
            rows.append(MarketNewsSearchRow(
                id=orm.id, title=orm.title, area_tag=orm.area_tag,
                source=orm.source, published_at=orm.published_at,
            ))
            if len(rows) >= limit:
                break
        return rows

    async def search_hybrid(
        self, embedding: list[float], query: str, limit: int = 4,
    ) -> list[MarketNewsSearchRow]:
        """벡터 코사인 + trigram 키워드 채널을 RRF로 결합한 검색 — R2 실험 경로.

        ⚠ 아직 프로덕션 경로가 아니다 — 유스케이스는 현행 search_similar(순수 코사인)를
        쓰고, 이 메서드는 평가 러너가 하이브리드 트레이스를 만드는 데 쓴다(stock
        news_pg_repository.search_hybrid와 같은 규칙 — 게이트 통과 시에만 전환).
        """
        title_sim = func.similarity(MarketNewsArticleOrm.title, query)
        channel_stmts = (
            select(MarketNewsArticleOrm)
            .where(MarketNewsArticleOrm.embedding.is_not(None))
            .order_by(MarketNewsArticleOrm.embedding.cosine_distance(embedding))
            .limit(HYBRID_CHANNEL_LIMIT * 2),
            # trigram 겹침이 전혀 없는 행(similarity 0)은 순위 잡음이라 거른다
            select(MarketNewsArticleOrm)
            .where(title_sim > 0)
            .order_by(title_sim.desc())
            .limit(HYBRID_CHANNEL_LIMIT * 2),
        )
        row_by_id: dict[int, MarketNewsSearchRow] = {}
        channels: list[list[int]] = []
        for stmt in channel_stmts:
            result = await self._session.execute(stmt)
            ids: list[int] = []
            seen: set[str] = set()
            for orm in result.scalars().all():
                if orm.title in seen:  # (url, area_tag) 유니크 구조상 같은 제목 다행 — 채널 내 dedupe
                    continue
                seen.add(orm.title)
                row_by_id[orm.id] = MarketNewsSearchRow(
                    id=orm.id, title=orm.title, area_tag=orm.area_tag,
                    source=orm.source, published_at=orm.published_at,
                )
                ids.append(orm.id)
                if len(ids) >= HYBRID_CHANNEL_LIMIT:
                    break
            channels.append(ids)
        # 채널 간 같은 제목이 다른 id로 올 수 있다 — 최종 조립에서 제목 dedupe
        rows: list[MarketNewsSearchRow] = []
        seen_titles: set[str] = set()
        for doc_id in rrf_merge(channels):
            row = row_by_id[doc_id]
            if row.title in seen_titles:
                continue
            seen_titles.add(row.title)
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows
