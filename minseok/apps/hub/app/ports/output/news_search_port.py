from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.news_dto import NewsHit, NewsKeyword


class NewsSearchPort(ABC):
    """허브가 스포크에 위임하는 뉴스 의미 검색 추상.

    계약은 자연어 질의 → 히트다(임베딩은 구현 스포크의 세부 — 모델 교체가 계약에
    누설되지 않는다). 허브는 이 포트(추상)만 알고 어떤 스포크가 구현하는지 모른다.
    구현은 스포크(stock)가 제공하고, 합성 루트(main.py)에서 주입한다.
    """

    @abstractmethod
    async def search(self, query: str, ticker: str | None = None, limit: int = 5) -> list[NewsHit]:
        """질의와 의미가 가까운 수집 뉴스를 반환한다. 검색 불가(임베딩 미가용)면 빈 리스트."""
        ...

    @abstractmethod
    async def top_keywords(self, ticker: str, limit: int = 5) -> list[NewsKeyword]:
        """종목 최근 헤드라인의 영향 키워드 Top-N(B2, 결정론 — LLM 미사용).

        표본 미달·데이터 없음이면 빈 리스트(소비자는 라인 생략 — 열화 동작)."""
        ...
