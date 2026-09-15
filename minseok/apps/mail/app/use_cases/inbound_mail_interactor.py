from __future__ import annotations

import logging

from mail.app.ports.input.inbound_mail_use_case import InboundMailUseCase
from mail.app.ports.output.embedding_port import EmbeddingPort
from mail.app.ports.output.inbound_mail_repository import InboundMailRepositoryPort
from mail.domain.entities.inbound_mail import InboundMail

logger = logging.getLogger(__name__)


class InboundMailInteractor(InboundMailUseCase):
    """수신 메일 대장 — 임베딩 생성(pgvector) + 저장(중복 무시) + 조회/의미 검색."""

    def __init__(
        self,
        repository: InboundMailRepositoryPort,
        embeddings: EmbeddingPort | None = None,
    ) -> None:
        self._repository = repository
        self._embeddings = embeddings

    async def receive(self, mail: InboundMail) -> bool:
        embedding = await self._embed_or_none(f"{mail.subject}\n{mail.preview}")
        saved = await self._repository.save(mail, embedding=embedding)
        logger.info(
            "[mail] 수신 %s → %s (임베딩 %s)",
            mail.message_id, "신규 저장" if saved else "중복 무시",
            "생성" if embedding else "없음",
        )
        return saved

    async def list_mails(self, limit: int = 50) -> list[InboundMail]:
        return await self._repository.list_recent(limit)

    async def search_mails(self, query: str, limit: int = 5) -> list[InboundMail]:
        if self._embeddings is None:
            return []
        embedding = await self._embeddings.embed(query)
        return await self._repository.search_similar(embedding, limit)

    async def _embed_or_none(self, text: str) -> list[float] | None:
        """임베딩 실패가 메일 수신을 막으면 안 된다 — 실패 시 NULL로 저장."""
        if self._embeddings is None:
            return None
        try:
            return await self._embeddings.embed(text, kind="document")
        except Exception:
            logger.warning("[mail] 임베딩 생성 실패 — 벡터 없이 저장", exc_info=True)
            return None
