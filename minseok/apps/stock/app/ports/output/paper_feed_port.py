from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from stock.app.dtos.paper_dto import NewsFeedRow, SnapshotFeedRow
from stock.domain.entities.price_bar import PriceBar


class PaperFeedPort(ABC):
    """모의투자가 읽는 시세·신호·뉴스 — 전부 저장 데이터(벤더 호출 없음).

    **as_of 이전만 본다는 규칙은 이 포트의 계약이다.** 시각 인자를 받는 메서드는 그 시각 이후
    행을 절대 돌려주지 않는다(리플레이 정직성 — 테스트로 고정).
    """

    @abstractmethod
    async def snapshots_on(self, day: date, horizon: int) -> list[SnapshotFeedRow]:
        """그날(UTC 날짜) 캡처된 티커별 스냅샷. 없으면 빈 리스트."""
        ...

    @abstractmethod
    async def bars_after(self, ticker: str, after: datetime, until: datetime, limit: int) -> list[PriceBar]:
        """after < ts ≤ until 인 1d 봉을 오름차순으로 최대 limit개."""
        ...

    @abstractmethod
    async def bars_until(self, ticker: str, until: datetime, limit: int) -> list[PriceBar]:
        """ts ≤ until 인 최근 1d 봉 limit개(오름차순)."""
        ...

    @abstractmethod
    async def latest_close(self, ticker: str) -> tuple[float, datetime] | None:
        """가장 최근 봉 종가(5분봉 우선, 없으면 일봉) — 사람 주문 체결가."""
        ...

    @abstractmethod
    async def news_between(self, ticker: str, since: datetime, until: datetime, limit: int) -> list[NewsFeedRow]:
        """since ≤ published_at ≤ until 라벨 조인 뉴스(최신순)."""
        ...

    @abstractmethod
    async def spy_closes(self, until: datetime) -> list[PriceBar]:
        """SPY 1d 봉 전체(ts ≤ until) — 기준선."""
        ...
