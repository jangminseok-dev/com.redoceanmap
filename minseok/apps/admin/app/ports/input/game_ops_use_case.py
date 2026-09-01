from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.game_ops_dto import (
    GameOpsBoard,
    GameWalletQuery,
    GameWalletView,
    GrantCapitalCommand,
    GrantCapitalResult,
    HideContentCommand,
    InterveneCommand,
    InterventionView,
    ReportedContentView,
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

    @abstractmethod
    async def list_reported(self, limit: int = 50) -> tuple[ReportedContentView, ...]:
        """토론방 신고 대기줄(최근 신고순). 이미 내려간 것도 포함한다."""
        ...

    @abstractmethod
    async def hide_content(self, command: HideContentCommand) -> None:
        """신고된 글·댓글을 내린다. 대상이 없거나 이미 내려갔으면 ValueError."""
        ...

    @abstractmethod
    async def unhide_content(self, target_type: str, target_id: int, actor_id: int) -> None:
        """숨김 해제. 대상이 없거나 숨겨져 있지 않으면 ValueError."""
        ...
