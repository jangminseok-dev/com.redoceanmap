from __future__ import annotations

from core.llm.llm_orchestrator import llm_orchestrator
from market.app.ports.output.embedding_port import EmbeddingPort


class OllamaEmbeddingAdapter(EmbeddingPort):
    """오케스트레이터의 임베딩 갈래(EMBED_MODEL, 768차원)로 수렴 — stock·market·mail 동일 패턴."""

    async def embed(self, text: str, *, kind: str = "query") -> list[float]:
        return await llm_orchestrator.embed(text, kind=kind)

    async def embed_many(self, texts: list[str], *, kind: str = "document") -> list[list[float]]:
        return await llm_orchestrator.embed_many(texts, kind=kind)
