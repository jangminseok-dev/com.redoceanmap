from sqlalchemy import BigInteger, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameQuarterSettlementOrm(Base):
    """분기 결산 1건.

    일별 매출은 저장하지 않지만 **결산은 저장한다.** 분기 손익이 지갑에 반영되는 것은
    캐시가 아니라 게임 규칙상 실재하는 사건이기 때문이다(game-harness §4-2).
    유니크 제약이 같은 분기를 두 번 정산하는 것을 DB에서 막는다 — 지연 실행이라
    조회가 잦고, 멱등성이 곧 정확성이다.
    """

    __tablename__ = "game_quarter_settlements"
    __table_args__ = (
        UniqueConstraint("store_id", "game_quarter", name="uq_game_quarter_settlements"),
        Index("ix_game_quarter_settlements_store", "store_id", "game_quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("game_stores.id"), index=True)
    game_quarter: Mapped[int] = mapped_column(Integer)
    days_counted: Mapped[int] = mapped_column(Integer)

    total_sales_krw: Mapped[int] = mapped_column(BigInteger)
    total_rent_krw: Mapped[int] = mapped_column(BigInteger)
    total_labor_krw: Mapped[int] = mapped_column(BigInteger)
    total_cogs_krw: Mapped[int] = mapped_column(BigInteger)
    total_utility_krw: Mapped[int] = mapped_column(BigInteger)
    profit_krw: Mapped[int] = mapped_column(BigInteger)

    payload: Mapped[dict] = mapped_column(JSONB)  # 손님 수·반려율·성과배율·조언
    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
