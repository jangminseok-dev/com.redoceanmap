from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.rulebook_dto import RulebookQuery, RulebookResponse


class RulebookUseCase(ABC):
    """게임 (game) 유스케이스 — 게임 규칙·제약 안내와 현재 게임 시각 제공."""

    @abstractmethod
    async def introduce_myself(self, query: RulebookQuery) -> RulebookResponse:
        """게임 (game)의 자기소개 메소드."""
        ...
