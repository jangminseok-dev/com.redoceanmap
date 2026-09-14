from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_public_dto import AreaIndexRow, AreaPublicView


class AreaPublicUseCase(ABC):
    """비로그인 공개 상권 페이지(A-4) — 상권 1곳 요약과 sitemap용 인덱스."""

    @abstractmethod
    async def get_public(self, trdar_code: int) -> AreaPublicView | None:
        """상권이 없으면 None(HTTP 변환은 라우터 몫)."""
        ...

    @abstractmethod
    async def list_index(self) -> list[AreaIndexRow]:
        """전 상권 코드·이름·자치구·유형 — sitemap 생성용."""
        ...
