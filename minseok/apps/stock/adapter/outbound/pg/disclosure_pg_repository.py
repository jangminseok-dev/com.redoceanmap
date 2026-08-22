from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.disclosure_chunk_orm import DisclosureChunkOrm
from stock.domain.services.disclosure_chunker import Chunk


@dataclass(frozen=True)
class DisclosureHit:
    """청크 검색 히트 1건 — R3 러너가 트레이스·라벨링 시트를 만드는 데 쓴다."""

    id: int
    corp_name: str
    rcept_no: str
    strategy: str
    section_path: str
    kind: str
    content: str


class DisclosurePgRepository:
    """disclosure_chunks 적재·검색 — R3 실험 전용(프로덕션 포트 없음, search_hybrid 선례).

    적재는 (rcept_no, strategy) 단위 교체 멱등 — 같은 문서 재청킹이 안전하다.
    검색은 전략별 코사인 브루트포스(수천 청크 — 인덱스 불요).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_chunks(
        self, corp_code: str, corp_name: str, rcept_no: str,
        strategy: str, chunks: list[Chunk],
    ) -> int:
        await self._session.execute(
            delete(DisclosureChunkOrm).where(
                DisclosureChunkOrm.rcept_no == rcept_no,
                DisclosureChunkOrm.strategy == strategy,
            )
        )
        self._session.add_all([
            DisclosureChunkOrm(
                corp_code=corp_code, corp_name=corp_name, rcept_no=rcept_no,
                strategy=strategy, section_path=c.section_path[:300],
                chunk_index=i, kind=c.kind, content=c.content,
            )
            for i, c in enumerate(chunks)
        ])
        await self._session.commit()
        return len(chunks)

    async def unembedded(self, strategy: str, limit: int = 500) -> list[DisclosureChunkOrm]:
        return list((await self._session.execute(
            select(DisclosureChunkOrm)
            .where(
                DisclosureChunkOrm.strategy == strategy,
                DisclosureChunkOrm.embedding.is_(None),
            )
            .order_by(DisclosureChunkOrm.id)
            .limit(limit)
        )).scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def search_similar(
        self, embedding: list[float], strategy: str, limit: int = 20,
    ) -> list[DisclosureHit]:
        rows = (await self._session.execute(
            select(DisclosureChunkOrm)
            .where(
                DisclosureChunkOrm.strategy == strategy,
                DisclosureChunkOrm.embedding.is_not(None),
            )
            .order_by(DisclosureChunkOrm.embedding.cosine_distance(embedding))
            .limit(limit)
        )).scalars().all()
        return [
            DisclosureHit(
                id=r.id, corp_name=r.corp_name, rcept_no=r.rcept_no,
                strategy=r.strategy, section_path=r.section_path,
                kind=r.kind, content=r.content,
            )
            for r in rows
        ]
