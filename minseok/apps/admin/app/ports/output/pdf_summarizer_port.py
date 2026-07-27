from __future__ import annotations

from abc import ABC, abstractmethod


class PdfSummarizerPort(ABC):
    """추출 텍스트를 요약하는 아웃바운드 포트.

    구현체는 LLM 오케스트레이터(EXAONE 7.8B) 경유 어댑터다 — app 계층은 모델을 모른다.
    """

    @abstractmethod
    async def summarize(self, title: str, text: str) -> str:
        """문서 요약문을 반환한다."""
        ...
