from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PaperAccountOrm(Base):
    """모의투자 참가 계정 — exaone·signal(각 1개)·user(사용자당 1개). 현금은 여기 산다."""

    __tablename__ = "paper_accounts"
    __table_args__ = (
        # 사용자 계정은 (kind, user_id) 유니크, AI 계정은 kind당 1행(user_id NULL) — NULL은 유니크에 안 걸려 부분 인덱스로 막는다
        UniqueConstraint("kind", "user_id", name="uq_paper_accounts_kind_user"),
        Index("uq_paper_accounts_kind_ai", "kind", unique=True, postgresql_where=text("user_id IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))  # exaone | signal | user
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cash_krw: Mapped[float] = mapped_column(Float)
    initial_cash_krw: Mapped[float] = mapped_column(Float)
    started_on: Mapped[date] = mapped_column(Date)
    rules_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperPositionOrm(Base):
    """열린 포지션 — 청산되면 행이 사라진다(이력은 paper_trades)."""

    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "ticker", "side", name="uq_paper_positions_account_ticker_side"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    ticker: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(5))  # LONG | SHORT
    quantity: Mapped[int] = mapped_column(BigInteger)
    avg_price: Mapped[float] = mapped_column(Float)  # 종목 통화
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
