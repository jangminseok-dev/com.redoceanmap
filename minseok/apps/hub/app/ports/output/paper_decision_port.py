from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.paper_trading_dto import PaperDecisionInfo


class PaperDecisionPort(ABC):
    """모의투자 최근 판단 조회 계약 — chat(소비)과 stock(구현)을 잇는다.

    답변은 기록 보고("EXAONE 계정이 오늘 A를 샀다")까지다 — 권유 문형은 소비자 책임으로 금지.
    """

    @abstractmethod
    async def latest(self, accounts: list[str]) -> list[PaperDecisionInfo]:
        """계정 키별 최신 판단 1건. 판단이 없는 계정은 결과에서 빠진다."""
        ...
