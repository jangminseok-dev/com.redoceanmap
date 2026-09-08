from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PaperTradeOrm(Base):
    """체결 원장 — 사실만 남긴다. decision_id가 있으면 AI 판단의 체결, 없으면 사람 주문."""

    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(5))
    action: Mapped[str] = mapped_column(String(5))  # BUY | SELL | SHORT | COVER
    quantity: Mapped[int] = mapped_column(BigInteger)
    price: Mapped[float] = mapped_column(Float)  # 종목 통화
    fee_krw: Mapped[float] = mapped_column(Float)
    realized_pnl_krw: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decision_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {news_ids, signals}
    replayed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
