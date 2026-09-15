from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

EMBEDDING_DIM = 768  # embeddinggemma (2026-09-15, bge-m3 1024에서 교체)


class InboundMailOrm(Base):
    __tablename__ = "inbound_mails"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(200), unique=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    sender: Mapped[str] = mapped_column(String(300), default="")
    recipient: Mapped[str] = mapped_column(String(300), default="")
    preview: Mapped[str] = mapped_column(Text, default="")
    # 제목+본문 임베딩(bge-m3, 1024차원) — 의미 검색용. 임베딩 실패 시 NULL 허용(수신이 우선).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
