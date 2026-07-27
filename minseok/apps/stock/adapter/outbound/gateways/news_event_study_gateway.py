from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.news_event_study_dto import EventBucketRow, NewsEventStudyInfo
from hub.app.ports.output.news_event_study_port import NewsEventStudyPort
from stock.adapter.outbound.orm.news_event_study_report_orm import NewsEventStudyReportOrm


def _buckets(rows: list[dict]) -> list[EventBucketRow]:
    return [
        EventBucketRow(
            key=b.get("key", ""),
            n=b.get("n", 0),
            avg_return_pct=b.get("avg_return_pct", 0.0),
            excess_pct=b.get("excess_pct", 0.0),
            positive_rate=b.get("positive_rate", 0.0),
            reliable=b.get("reliable", False),
        )
        for b in rows
    ]


class NewsEventStudyGateway(NewsEventStudyPort):
    """허브 NewsEventStudyPort 구현 — 최신 실행 1행의 payload를 계약 DTO로 매핑.

    payload 키는 stock/domain/services/event_study.py가 정의 —
    누락 키는 .get() 관용(구버전 리포트 공존, AreaBacktestReportGateway 선례).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest(self) -> NewsEventStudyInfo | None:
        row = (await self._session.execute(
            select(NewsEventStudyReportOrm).order_by(NewsEventStudyReportOrm.id.desc()).limit(1)
        )).scalar()
        if row is None:
            return None
        payload = row.payload or {}
        return NewsEventStudyInfo(
            ran_at=row.ran_at,
            params=row.params or {},
            horizon_days=payload.get("horizon_days", 0),
            total=payload.get("total", 0),
            baseline_pct=payload.get("baseline_pct", 0.0),
            top_week_share=payload.get("top_week_share", 0.0),
            warnings=payload.get("warnings", []),
            by_event=_buckets(payload.get("by_event", [])),
            by_sentiment=_buckets(payload.get("by_sentiment", [])),
        )
