from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameCommunityCommentOrm(Base):
    """토론방 글에 달린 댓글 1건.

    글과 같은 삭제·숨김 규칙을 쓴다(→ `game_community_post_orm`). 대댓글은 없다 —
    깊이가 생기면 화면·정렬·삭제 전파가 전부 두 배가 되는데, 종목 토론방에서
    한 단계 이상이 필요했던 적이 없다.

    **글을 지워도 댓글을 지우지 않는다.** 목록 조회가 글에서 시작하므로 자연히 함께
    사라지고, 지워버리면 신고된 댓글의 이력이 글 삭제로 증발한다.
    """

    __tablename__ = "game_community_comments"
    __table_args__ = (
        # 조회는 항상 "이 글의 댓글 전부"로 들어간다
        Index("ix_game_community_comments_post", "post_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_community_posts.id"), index=False
    )
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유).
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    epoch_id: Mapped[int] = mapped_column(Integer)

    body: Mapped[str] = mapped_column(Text)

    created_tick: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
