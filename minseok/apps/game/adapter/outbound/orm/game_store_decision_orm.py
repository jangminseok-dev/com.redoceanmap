from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameStoreDecisionOrm(Base):
    """가게 운영 결정 — **결정론 재계산의 입력**이다.

    일일 매출은 저장하지 않는다. 창업 시각과 이 결정들만 있으면 어느 날이든 다시 계산된다
    (game-harness §1-A). 결정을 바꾸면 그날부터 적용되고 과거는 그대로다 —
    `effective_from_day`가 그 경계다.

    payload: `{"price_factor": 1.0, "staff_count": 2, "facility_score": 300}`
    """

    __tablename__ = "game_store_decisions"
    __table_args__ = (
        Index("ix_game_store_decisions_store_day", "store_id", "effective_from_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("game_stores.id"), index=True)
    effective_from_day: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
