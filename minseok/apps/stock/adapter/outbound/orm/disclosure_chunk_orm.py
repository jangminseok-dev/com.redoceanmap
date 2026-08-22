from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

EMBEDDING_DIM = 1024  # bge-m3


class DisclosureChunkOrm(Base):
    """DART 사업보고서 청크 — R3 청킹 전략 비교 실험 코퍼스.

    같은 문서(rcept_no)를 전략별(a 고정 토큰 대조군 / b 섹션 분할 / c 표 인지)로
    따로 청킹해 나란히 저장한다 — 검색 품질 비교가 목적이라 strategy가 조회 축이다.
    적재는 scripts/collect_disclosures.py가 (rcept_no, strategy) 단위 교체로 멱등.
    """

    __tablename__ = "disclosure_chunks"
    __table_args__ = (
        UniqueConstraint(
            "rcept_no", "strategy", "chunk_index",
            name="uq_disclosure_chunks_doc_strategy_index",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    corp_code: Mapped[str] = mapped_column(String(8))      # DART 고유번호
    corp_name: Mapped[str] = mapped_column(String(40))     # 표시·질의 대조용
    rcept_no: Mapped[str] = mapped_column(String(14))      # 접수번호(문서 키)
    strategy: Mapped[str] = mapped_column(String(1), index=True)  # a | b | c
    section_path: Mapped[str] = mapped_column(String(300), default="")
    chunk_index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))           # text | table
    content: Mapped[str] = mapped_column(Text)
    # 청크 임베딩. 실패 시 NULL — 적재 우선, --embed 재실행이 자연 재시도(news 패턴)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
