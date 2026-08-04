"""허브 QuestionInsightPort를 chat(스포크)이 구현한다.

admin은 chat을 직접 import할 수 없으므로(스타 토폴로지) 이 파일이 유일한 접점이다.
chat이 이미 영속하는 conversations/messages를 읽기만 한다 — 새 테이블 없음.

답변 종류(answer_kind)는 별도 저장이 아니라 **관측으로 유도**한다:
- assistant payload 키(recommendations/stock/news)가 라우팅 결과를 그대로 남긴다
- 서울 외 가드는 고정 접두(NONSEOUL_GUARD_PREFIX — 인터랙터가 정의)로 식별한다
저장 스키마를 늘리지 않는 대신, 과거 대화까지 소급 집계된다는 이점이 있다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.adapter.outbound.orm.conversation_orm import MessageOrm
from chat.app.use_cases.chat_interactor import NON_SEOUL_REGIONS, NONSEOUL_GUARD_PREFIX
from hub.app.dtos.question_insight_dto import (
    KindCount,
    QuestionInsightStats,
    QuestionRecord,
    RegionDemand,
)
from hub.app.ports.output.question_insight_port import QuestionInsightPort


def infer_answer_kind(payload: dict | None, content: str) -> str:
    """assistant 메시지 1건 → 답변 종류. 순수 함수(테스트는 DB 없이 이걸 잡는다)."""
    if content.startswith(NONSEOUL_GUARD_PREFIX):
        return "nonseoul"
    if payload:
        if "recommendations" in payload:
            return "market"
        if "stock" in payload:
            return "stock"
        if "news" in payload:
            return "market_news"
    return "text"  # general·가드 외 안내·뉴스 히트 없는 market_news 등


def extract_region(question: str) -> str | None:
    """질문에서 서울 외 지역명 첫 매치 — 가드와 같은 목록(NON_SEOUL_REGIONS)을 쓴다."""
    return next((r for r in NON_SEOUL_REGIONS if r in question), None)


class QuestionInsightGateway(QuestionInsightPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def recent_questions(self, limit: int = 50) -> tuple[QuestionRecord, ...]:
        users = (await self._session.execute(
            select(MessageOrm.id, MessageOrm.conversation_id,
                   MessageOrm.content, MessageOrm.created_at)
            .where(MessageOrm.role == "user")
            .order_by(MessageOrm.id.desc())
            .limit(limit)
        )).all()
        if not users:
            return ()

        conv_ids = {u.conversation_id for u in users}
        assistants = (await self._session.execute(
            select(MessageOrm.id, MessageOrm.conversation_id,
                   MessageOrm.content, MessageOrm.payload)
            .where(MessageOrm.role == "assistant",
                   MessageOrm.conversation_id.in_(conv_ids),
                   MessageOrm.id > min(u.id for u in users))
            .order_by(MessageOrm.id)
        )).all()

        records = []
        for u in users:
            # 같은 대화에서 질문 직후의 첫 assistant 답 — 멀티턴에서도 짝이 맞는다
            reply = next(
                (a for a in assistants
                 if a.conversation_id == u.conversation_id and a.id > u.id),
                None,
            )
            records.append(QuestionRecord(
                conversation_id=u.conversation_id,
                question=u.content,
                answer_kind=(
                    infer_answer_kind(reply.payload, reply.content)
                    if reply else "text"
                ),
                asked_at=u.created_at,
            ))
        return tuple(records)

    async def stats(self, days: int = 30) -> QuestionInsightStats:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        total = (await self._session.execute(
            select(func.count()).select_from(MessageOrm)
            .where(MessageOrm.role == "user", MessageOrm.created_at >= cutoff)
        )).scalar_one()

        assistants = (await self._session.execute(
            select(MessageOrm.id, MessageOrm.conversation_id,
                   MessageOrm.content, MessageOrm.payload)
            .where(MessageOrm.role == "assistant", MessageOrm.created_at >= cutoff)
        )).all()

        kind_counts: dict[str, int] = {}
        guards = []
        for a in assistants:
            kind = infer_answer_kind(a.payload, a.content)
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            if kind == "nonseoul":
                guards.append(a)

        # 가드 답의 직전 user 질문에서 지역을 뽑는다 — 차단당한 실수요만 센다
        region_counts: dict[str, int] = {}
        if guards:
            users = (await self._session.execute(
                select(MessageOrm.id, MessageOrm.conversation_id, MessageOrm.content)
                .where(MessageOrm.role == "user",
                       MessageOrm.conversation_id.in_({g.conversation_id for g in guards}),
                       MessageOrm.created_at >= cutoff)
            )).all()
            for g in guards:
                question = max(
                    (u for u in users
                     if u.conversation_id == g.conversation_id and u.id < g.id),
                    key=lambda u: u.id, default=None,
                )
                region = extract_region(question.content) if question else None
                if region:
                    region_counts[region] = region_counts.get(region, 0) + 1

        return QuestionInsightStats(
            window_days=days,
            total_questions=total,
            kind_counts=tuple(
                KindCount(kind=k, count=c)
                for k, c in sorted(kind_counts.items(), key=lambda kv: -kv[1])
            ),
            nonseoul_regions=tuple(
                RegionDemand(region=r, count=c)
                for r, c in sorted(region_counts.items(), key=lambda kv: -kv[1])
            ),
        )
