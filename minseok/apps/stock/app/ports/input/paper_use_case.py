from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from stock.app.dtos.paper_dto import (
    AccountView,
    BoardView,
    DecisionView,
    ScorecardView,
    StepCommand,
    StepResult,
)


class PaperUseCase(ABC):
    """AI 모의투자 — 배치 step, 리더보드·계정·판단·채점 조회."""

    @abstractmethod
    async def step(self, cmd: StepCommand) -> StepResult: ...

    @abstractmethod
    async def board(self) -> BoardView: ...

    @abstractmethod
    async def account(self, key: str) -> AccountView | None:
        """key = exaone | signal. 없으면 None."""
        ...

    @abstractmethod
    async def decisions(self, key: str, since: date | None, until: date | None, limit: int) -> list[DecisionView]: ...

    @abstractmethod
    async def scorecard(self, key: str) -> ScorecardView | None: ...
