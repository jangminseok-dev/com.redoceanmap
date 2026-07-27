"""요약된 PDF 문서 — admin 자체 소유 테이블(감사 로그에 이은 두 번째).

다른 스포크 데이터가 아니라 어드민 콘솔에서 업로드한 운영 문서라 허브 경유 없이 직접 영속한다.
업로드된 PDF 바이너리 자체는 보관하지 않는다(추출 텍스트 + 요약만) — S3 적재는 범위 밖.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PdfDocumentOrm(Base):
    __tablename__ = "admin_pdf_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    extracted_text: Mapped[str] = mapped_column(Text)  # 추출 원문(재요약·검색 재료)
    summary: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
