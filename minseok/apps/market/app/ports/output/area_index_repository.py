from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_public_dto import AreaIndexRow


class AreaIndexRepositoryPort(ABC):
    """상권 차원 목록(코드·이름·자치구·유형) 조회 — 공개 페이지의 헤더와 sitemap이 쓴다."""

    @abstractmethod
    async def find_one(self, trdar_code: int) -> AreaIndexRow | None:
        ...

    @abstractmethod
    async def list_all(self) -> list[AreaIndexRow]:
        """코드 오름차순 전 상권."""
        ...
