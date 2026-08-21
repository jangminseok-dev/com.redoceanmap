from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class BookmarkOrm(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        # 같은 대상을 두 번 찜할 수 없다 — 재등록은 upsert가 기존 행을 돌려준다(토글 멱등)
        UniqueConstraint(
            "user_id", "target_type", "target_key",
            name="uq_bookmarks_user_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    target_type: Mapped[str] = mapped_column(String(8))    # stock | area
    target_key: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
