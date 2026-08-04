from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameCommunityPostOrm(Base):
    """종목 토론방 글 1건.

    게임의 다른 값과 달리 **저장한다** — 사람이 쓴 문장은 시각의 함수로 유도할 수 없다
    (관리자 개입이 저장되는 것과 같은 근거, harness §1-A).

    **작성자 이름은 저장하지 않는다.** `user_id`에서 `domain/community/nickname.py`가
    결정론으로 유도한다 — 실명 노출을 막고, 같은 사람의 옛 글과 새 글이 다른 이름을
    갖는 사고도 함께 막는다.

    지우는 방법이 둘이고 **서로 구분된다**:
    - `deleted_at` — 작성자 본인이 지웠다. 목록에서 사라진다.
    - `hidden_at` — 어드민이 숨겼다. 사유(`hidden_reason`)가 남고, 신고 처리 이력이 된다.
      본인 삭제와 한 컬럼에 섞으면 "누가 왜 내렸나"를 사후에 답할 수 없다.
    """

    __tablename__ = "game_community_posts"
    __table_args__ = (
        # 토론방은 항상 "이 종목의 최신 글"로 열린다
        Index("ix_game_community_posts_symbol_created", "symbol", "created_at"),
        Index("ix_game_community_posts_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유).
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    epoch_id: Mapped[int] = mapped_column(Integer)

    symbol: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)

    created_tick: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
