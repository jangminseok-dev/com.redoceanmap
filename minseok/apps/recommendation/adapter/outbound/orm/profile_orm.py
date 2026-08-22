from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InvestorProfileOrm(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 사용자당 1행 — 설문 재작성은 upsert가 전 필드를 덮어쓴다
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(8))       # startup | invest | both
    risk_level: Mapped[int] = mapped_column(Integer)      # 1~5 (투자성향 5등급)
    budget_band: Mapped[str] = mapped_column(String(16))  # under_30m ~ over_300m (밴드만 — 정확 금액 미보유)
    debt_burden: Mapped[str] = mapped_column(String(12))  # none | manageable | heavy
    horizon: Mapped[str] = mapped_column(String(8))       # short | mid | long
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
