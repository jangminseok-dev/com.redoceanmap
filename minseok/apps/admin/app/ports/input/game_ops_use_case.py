from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.game_ops_dto import (
    GameOpsBoard,
    GameWalletQuery,
    GameWalletView,
    GrantCapitalCommand,
    GrantCapitalResult,
    InterveneCommand,
    InterventionView,
)


class GameOpsUseCase(ABC):
    """게임 운영 — 자본 지급과 주가 개입."""

    @abstractmethod
    async def get_wallet(self, query: GameWalletQuery) -> GameWalletView:
        ...

    @abstractmethod
    async def grant_capital(self, command: GrantCapitalCommand) -> GrantCapitalResult:
        ...

    @abstractmethod
    async def get_board(self) -> GameOpsBoard:
        ...

    @abstractmethod
    async def intervene(self, command: InterveneCommand) -> InterventionView:
        ...
