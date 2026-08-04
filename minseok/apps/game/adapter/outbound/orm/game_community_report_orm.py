from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameCommunityReportOrm(Base):
    """신고 1건 — 글 또는 댓글을 어드민 검토 대기줄에 올린다.

    신고가 곧 숨김이 **아니다.** 신고는 접수만 하고 내리는 판단은 어드민이 한다 —
    자동 숨김을 두면 여럿이 몰려 신고하는 것만으로 남의 글을 내릴 수 있다.

    글·댓글을 한 테이블에서 받는다(`target_type`). 둘로 나누면 어드민 대기줄이
    두 쿼리가 되는데, 신고에 담긴 정보가 양쪽 같아서 나눌 이유가 없다. 대신
    **FK를 걸 수 없다** — 두 테이블을 가리키므로 대상 존재 확인은 유스케이스가 한다.

    같은 사람이 같은 대상을 여러 번 신고해도 1건이다(유니크) — 신고 수가 곧
    검토 우선순위인데 한 사람이 반복 신고로 그 순위를 만들 수 있으면 안 된다.
    """

    __tablename__ = "game_community_reports"
    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "target_id",
            "reporter_user_id",
            name="uq_game_community_reports_target_reporter",
        ),
        # 어드민 대기줄 = 미처리 신고를 대상별로 묶어 본다
        Index("ix_game_community_reports_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(8))  # post | comment
    target_id: Mapped[int] = mapped_column(Integer)

    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유).
    reporter_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
