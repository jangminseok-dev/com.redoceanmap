from __future__ import annotations

from abc import ABC, abstractmethod


class PdfTextExtractorPort(ABC):
    """PDF 바이트에서 텍스트 레이어를 추출하는 아웃바운드 포트.

    구현체(neo4j-graphrag PdfLoader)는 어댑터 계층에만 존재한다 —
    app 계층은 "바이트를 주면 텍스트가 나온다"는 계약만 안다.
    """

    @abstractmethod
    async def extract(self, filename: str, content: bytes) -> str:
        """추출된 전체 텍스트를 반환한다. 추출 자체가 실패하면 PdfExtractionError."""
        ...
