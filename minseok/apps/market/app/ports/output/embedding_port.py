from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    """텍스트 임베딩 아웃바운드 포트(pgvector 저장·검색용). 구현은 어댑터가 제공.

    kind는 "query"(검색 질의) | "document"(적재 문서). 프롬프트를 쓰는 임베딩 모델(embeddinggemma)은
    둘을 구분해야 저장 벡터와 질의 벡터가 같은 공간에 놓인다(2026-09-15 bge-m3 → embeddinggemma).
    """

    @abstractmethod
    async def embed(self, text: str, *, kind: str = "query") -> list[float]:
        """단건 임베딩 — 기본은 검색 질의."""
        ...

    @abstractmethod
    async def embed_many(self, texts: list[str], *, kind: str = "document") -> list[list[float]]:
        """적재 배치 임베딩 — HTTP 1콜로 여러 건 처리. 기본은 문서."""
        ...
