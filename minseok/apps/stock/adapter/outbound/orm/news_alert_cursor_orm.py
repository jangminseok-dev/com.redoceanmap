from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class NewsAlertCursorOrm(Base):
    """B9 뉴스 알림 워터마크 — 마지막으로 처리한 news_labels.id, 단일 행(id=1).

    dedupe를 배달 기록이 아니라 커서로 푼다: 커서 이후 적재분만 알림 후보가 되므로
    같은 뉴스가 두 번 나갈 수 없다. `user_alert_deliveries`를 쓰지 않는 이유는
    가격 알림과 동일(북마크 스캔의 전체 교체와 충돌 — n3a4b5c6d7e8 마이그레이션 주석).
    """

    __tablename__ = "news_alert_cursor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_label_id: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
