from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_errors import is_infra_failure
from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.app.dtos.news_search_dto import NewsSearchRow
from stock.app.ports.output.news_repository import NewsRepositoryPort
from stock.domain.entities.news_article import NewsArticle
from stock.domain.services.rrf_fusion import rrf_merge

logger = logging.getLogger(__name__)

DEFAULT_LABELER = "exaone-7.8b"  # 검색 히트에 동반할 라벨 버전 — 상위 모델 도입 시 교체 지점

# 하이브리드 검색(R2) — 채널별 후보 폭. 라벨 확정 후 파라미터 스윕(R2 ③)의 조정 대상.
HYBRID_CHANNEL_LIMIT = 30


class NewsPgRepository(NewsRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, articles: list[NewsArticle]) -> int:
        """일괄 저장. 한 행이 거부돼도 배치 전체를 잃지 않도록 행 단위로 되짚는다."""
        if not articles:
            return 0
        try:
            return await self._insert(articles)
        except DBAPIError as e:
            if is_infra_failure(e):
                raise  # 행 문제가 아니다 — 되짚으면 전 행이 조용히 유실된다(n8n이 재시도하게)
            await self._session.rollback()
            return await self._insert_row_by_row(articles)

    async def _insert(self, articles: list[NewsArticle]) -> int:
        stmt = (
            pg_insert(NewsArticleOrm)
            .values([
                {
                    "title": a.title,
                    "source": a.source,
                    "url": a.url,
                    "ticker": a.ticker,
                    "published_at": a.published_at,
                }
                for a in articles
            ])
            .on_conflict_do_nothing(index_elements=["url", "ticker"])
            .returning(NewsArticleOrm.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return len(result.scalars().all())

    async def _insert_row_by_row(self, articles: list[NewsArticle]) -> int:
        saved = 0
        for a in articles:
            try:
                saved += await self._insert([a])
            except DBAPIError as e:
                if is_infra_failure(e):
                    raise  # 인프라 장애 — 남은 행도 전부 같은 이유로 실패한다
                await self._session.rollback()
                logger.warning(
                    "[stock-news] 행 거부 — 건너뜀 (ticker=%s, url %d자): %s",
                    a.ticker, len(a.url), e.orig,
                )
        return saved

    async def recent_titles(self, query: str, ticker: str = "", limit: int = 5) -> list[str]:
        # ticker 정확 일치(거래소 접미 포함) 우선 + 제목 부분 일치 폴백(티커 미기록 구버전 행)
        conditions = [NewsArticleOrm.title.ilike(f"%{query}%")]
        if ticker:
            conditions += [
                NewsArticleOrm.ticker == ticker,
                NewsArticleOrm.ticker.like(f"{ticker}.%"),
            ]
        stmt = (
            select(NewsArticleOrm.title)
            .where(or_(*conditions))
            .order_by(NewsArticleOrm.published_at.desc().nulls_last(), NewsArticleOrm.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def sentiment_baseline(self, ticker: str, days: int = 30) -> tuple[float | None, int]:
        since = datetime.now(UTC) - timedelta(days=days)
        avg, count = (await self._session.execute(
            select(func.avg(NewsLabelOrm.sentiment), func.count(NewsLabelOrm.id))
            .join(NewsArticleOrm, NewsLabelOrm.news_id == NewsArticleOrm.id)
            .where(
                or_(
                    NewsArticleOrm.ticker == ticker,
                    NewsArticleOrm.ticker.like(f"{ticker}.%"),  # 접미 매칭(005930 ↔ 005930.KS)
                ),
                NewsLabelOrm.labeler == DEFAULT_LABELER,
                NewsArticleOrm.published_at >= since,
            )
        )).one()
        return (float(avg) if avg is not None else None, int(count))

    async def unembedded(self, limit: int = 200) -> list[tuple[int, str]]:
        stmt = (
            select(NewsArticleOrm.id, NewsArticleOrm.title)
            .where(NewsArticleOrm.embedding.is_(None))
            .order_by(NewsArticleOrm.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row_id, title) for row_id, title in result.all()]

    async def set_embeddings(self, items: list[tuple[int, list[float]]]) -> int:
        if not items:
            return 0
        for row_id, embedding in items:
            await self._session.execute(
                update(NewsArticleOrm)
                .where(NewsArticleOrm.id == row_id)
                .values(embedding=embedding)
            )
        await self._session.commit()
        return len(items)

    async def search_similar(
        self, embedding: list[float], ticker: str | None = None, limit: int = 5,
    ) -> list[NewsSearchRow]:
        conditions = [NewsArticleOrm.embedding.is_not(None)]
        if ticker:
            # recent_titles와 동일한 거래소 접미 규칙(005930 ↔ 005930.KS)
            conditions.append(or_(
                NewsArticleOrm.ticker == ticker,
                NewsArticleOrm.ticker.like(f"{ticker}.%"),
            ))
        stmt = (
            select(NewsArticleOrm, NewsLabelOrm.sentiment, NewsLabelOrm.event_type)
            .outerjoin(NewsLabelOrm, and_(
                NewsLabelOrm.news_id == NewsArticleOrm.id,
                NewsLabelOrm.labeler == DEFAULT_LABELER,
            ))
            .where(*conditions)
            .order_by(NewsArticleOrm.embedding.cosine_distance(embedding))
            .limit(limit * 2)  # 같은 기사가 (url, ticker) 유니크 구조상 다행 존재 — 여유 조회 후 제목 dedupe
        )
        result = await self._session.execute(stmt)
        rows: list[NewsSearchRow] = []
        seen_titles: set[str] = set()
        for orm, sentiment, event_type in result.all():
            if orm.title in seen_titles:
                continue
            seen_titles.add(orm.title)
            rows.append(NewsSearchRow(
                id=orm.id, title=orm.title, ticker=orm.ticker, source=orm.source,
                published_at=orm.published_at, sentiment=sentiment, event_type=event_type,
            ))
            if len(rows) >= limit:
                break
        return rows

    async def search_hybrid(
        self, embedding: list[float], query: str,
        ticker: str | None = None, limit: int = 5,
    ) -> list[NewsSearchRow]:
        """벡터 코사인 + trigram 키워드 채널을 RRF로 결합한 검색 — R2 실험 경로.

        ⚠ 아직 프로덕션 경로가 아니다 — 유스케이스는 현행 search_similar(순수 코사인)를
        쓰고, 이 메서드는 평가 러너가 하이브리드 트레이스를 만드는 데 쓴다. R1 baseline
        대비 nDCG@5 +0.03 게이트 통과 시 포트·유스케이스 전환, 미달이면 기각(ROADMAP R2).
        키워드 채널은 문자 trigram(pg_trgm similarity)이라 형태소 분석이 아니다 —
        조사·띄어쓰기 변형에 강할 뿐 의미 확장은 벡터 채널 몫이다.
        """
        conditions = []
        if ticker:
            conditions.append(or_(
                NewsArticleOrm.ticker == ticker,
                NewsArticleOrm.ticker.like(f"{ticker}.%"),
            ))
        base = select(NewsArticleOrm, NewsLabelOrm.sentiment, NewsLabelOrm.event_type).outerjoin(
            NewsLabelOrm, and_(
                NewsLabelOrm.news_id == NewsArticleOrm.id,
                NewsLabelOrm.labeler == DEFAULT_LABELER,
            )
        )
        title_sim = func.similarity(NewsArticleOrm.title, query)
        channel_stmts = (
            base.where(NewsArticleOrm.embedding.is_not(None), *conditions)
            .order_by(NewsArticleOrm.embedding.cosine_distance(embedding))
            .limit(HYBRID_CHANNEL_LIMIT * 2),
            # trigram 겹침이 전혀 없는 행(similarity 0)은 순위 잡음이라 거른다
            base.where(title_sim > 0, *conditions)
            .order_by(title_sim.desc())
            .limit(HYBRID_CHANNEL_LIMIT * 2),
        )
        row_by_id: dict[int, NewsSearchRow] = {}
        channels: list[list[int]] = []
        for stmt in channel_stmts:
            result = await self._session.execute(stmt)
            ids: list[int] = []
            seen: set[str] = set()
            for orm, sentiment, event_type in result.all():
                if orm.title in seen:  # (url, ticker) 유니크 구조상 같은 제목 다행 — 채널 내 dedupe
                    continue
                seen.add(orm.title)
                row_by_id[orm.id] = NewsSearchRow(
                    id=orm.id, title=orm.title, ticker=orm.ticker, source=orm.source,
                    published_at=orm.published_at, sentiment=sentiment, event_type=event_type,
                )
                ids.append(orm.id)
                if len(ids) >= HYBRID_CHANNEL_LIMIT:
                    break
            channels.append(ids)
        # 채널 간 같은 제목이 다른 id로 올 수 있다(점수가 갈라지는 소폭 손해) — 최종 조립에서 제목 dedupe
        rows: list[NewsSearchRow] = []
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
