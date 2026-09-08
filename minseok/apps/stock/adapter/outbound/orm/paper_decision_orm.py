from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PaperDecisionOrm(Base):
    """일별 판단 — 프롬프트·원문 응답·주문·거부·후보 전부. "왜 샀는가" 화면의 원천."""

    __tablename__ = "paper_decisions"
    __table_args__ = (
        # 계정당 하루 한 판단 — step 재실행이 판단을 두 번 만들지 않는다
        UniqueConstraint("account_id", "as_of", name="uq_paper_decisions_account_as_of"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    model: Mapped[str] = mapped_column(String(40))
    prompt: Mapped[str] = mapped_column(Text)
    response_raw: Mapped[str] = mapped_column(Text)
    market_view: Mapped[str] = mapped_column(Text)
    orders: Mapped[list] = mapped_column(JSONB)
    rejected: Mapped[list] = mapped_column(JSONB)
    candidates: Mapped[list] = mapped_column(JSONB)  # 그날 후보 요약 — 되감기 화면 원천
    latency_ms: Mapped[int] = mapped_column(Integer)
    replayed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperDecisionScoreOrm(Base):
    """판단 사후 채점 — 진입 주문 1건당 1행. 적중 정의는 스냅샷 채점과 같다."""

    __tablename__ = "paper_decision_scores"
    __table_args__ = (
        UniqueConstraint("decision_id", "ticker", name="uq_paper_decision_scores_decision_ticker"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(Integer, index=True)
    ticker: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(5))
    reason_kind: Mapped[str] = mapped_column(String(12))  # news | indicator | mixed | none
    realized_return_pct: Mapped[float] = mapped_column(Float)
    hit: Mapped[bool] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
