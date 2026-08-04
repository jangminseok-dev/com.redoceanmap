from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GamePositionOrm(Base):
    """롱/숏 포지션 1건. 청산 전에는 `closed_tick`이 NULL이다.

    `entry_price_krw`는 **대조용 스냅샷**이다 — 정본은 가격 엔진의 계산식이고, 재계산값과
    어긋나면 캐시 불일치가 아니라 버그 알람이다(game-harness §4-2).
    """

    __tablename__ = "game_positions"
    __table_args__ = (
        # 열린 포지션 조회가 가장 잦다 — 지갑 화면이 매 폴링마다 부른다
        Index("ix_game_positions_user_open", "user_id", "closed_tick"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    quantity: Mapped[int] = mapped_column(Integer)

    leverage: Mapped[int] = mapped_column(Integer, server_default="1")
    # 만료는 레버리지에만 있다. 1배는 NULL이며 마감 판정 대상이 아니다.
    expires_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # user | liquidated | expired
    close_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)

    entry_tick: Mapped[int] = mapped_column(Integer)
    entry_price_krw: Mapped[int] = mapped_column(BigInteger)
    entry_fee_krw: Mapped[int] = mapped_column(BigInteger)

    closed_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_price_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    exit_fee_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    carry_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    realized_pnl_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
