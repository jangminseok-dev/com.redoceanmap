from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

EMBEDDING_DIM = 768  # embeddinggemma (2026-09-15, bge-m3 1024에서 교체)


class MarketNewsArticleOrm(Base):
    __tablename__ = "market_news_articles"
    __table_args__ = (
        # 같은 기사(url)라도 지역별 관련성은 별개 샘플 — 지역 어간(area_tag) 단위로 유니크
        UniqueConstraint("url", "area_tag", name="uq_market_news_articles_url_area"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)  # 원문 그대로 — 가공(접두·번역·요약) 저장 금지
    source: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str] = mapped_column(Text)  # Google News RSS는 쿼리를 base64로 감싸 1000자를 넘는다
    area_tag: Mapped[str] = mapped_column(String(50), default="", index=True)  # 지역 어간(예: 성수)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # 제목 임베딩(의미 검색용). 실패 시 NULL — 수집 우선, 다음 주기 자연 재시도(stock 뉴스 패턴)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
