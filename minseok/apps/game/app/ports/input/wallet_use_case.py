from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.wallet_dto import WalletQuery, WalletView


class WalletUseCase(ABC):
    """지갑 조회 유스케이스 — 현금·보유 포지션·총자산."""

    @abstractmethod
    async def get_wallet(self, query: WalletQuery) -> WalletView:
        """계정이 없으면 초기 자본으로 만들어 반환한다."""
        ...
