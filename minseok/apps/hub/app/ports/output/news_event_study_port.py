from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.news_event_study_dto import NewsEventStudyInfo


class NewsEventStudyPort(ABC):
    """뉴스 이벤트 사후 수익률 연구 리포트 조회 협력.

    쓰기는 오프라인 배치(`scripts/study_news_events.py`)가 DB에 직접 한다
    (`AreaBacktestReportPort`와 같은 선례) — 이 포트는 조회 전용.
    구현은 stock 게이트웨이, 소비는 admin의 analytics 인터랙터.
    """

    @abstractmethod
    async def latest(self) -> NewsEventStudyInfo | None:
        """최신 실행 리포트 1건 — 실행 이력이 없으면 None."""
        ...
