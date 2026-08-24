from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AlertSettingOrm(Base):
    """회원별 알림 수신 설정 — 행이 없으면 기본 수신(ON). 끈 사람만 false 행을 가진다."""

    __tablename__ = "user_alert_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_alert_settings_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    email_alerts: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # 텔레그램 chat_id(I-7) — 등록한 회원만 텔레그램으로도 받는다(이메일과 별개 채널,
    # 수신 토글은 email_alerts 하나가 전 채널을 다스린다). NULL = 미등록.
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertDeliveryOrm(Base):
    """마지막으로 통지한 (사용자, 종목, 방향) — 같은 신호 지속 중 반복 발송 방지(dedupe).

    스캔 1회가 전량이라 매 실행 전체 교체된다. 신호가 꺼지면 행이 사라지고,
    다음 재발생 때 새 알림이 나간다.
    """

    __tablename__ = "user_alert_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_alert_deliveries_user_ticker"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    ticker: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(8))  # UP | DOWN
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
