from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameLimitOrderOrm(Base):
    """지정가 주문 1건 — 진입 예약(ENTRY) 또는 청산 예약(EXIT, 익절·손절).

    체결 판정에 cron을 쓰지 않는다. 유저 요청이 도달할 때 `placed_tick ~ min(now, expires_tick)`
    구간만 훑어 첫 충족 틱을 찾는다(game-strategy §7-12). 만료가 곧 스캔 상한이라
    `expires_tick`은 성능 장치다 — 없으면 장기 미접속자의 판정 비용이 폭발한다.

    익절·손절 쌍(OCO)은 그룹 컬럼 없이 **같은 `position_id`** 로 묶는다.
    """

    __tablename__ = "game_limit_orders"
    __table_args__ = (
        # 판정은 항상 "이 유저의 대기 주문 전부"로 시작한다
        Index("ix_game_limit_orders_user_status", "user_id", "status"),
        Index("ix_game_limit_orders_position", "position_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유).
    # 단독 인덱스를 걸지 않는다 — 조회는 항상 (user_id, status) 복합으로 들어간다.
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    epoch_id: Mapped[int] = mapped_column(Integer)

    kind: Mapped[str] = mapped_column(String(8))  # ENTRY | EXIT
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    # EXIT일 때만 채워진다 — 대상 포지션.
    position_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("game_positions.id"), nullable=True
    )

    trigger: Mapped[str] = mapped_column(String(2))  # le(이하) | ge(이상)
    limit_price_krw: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer)
    leverage: Mapped[int] = mapped_column(Integer, server_default="1")

    placed_tick: Mapped[int] = mapped_column(Integer)
    expires_tick: Mapped[int] = mapped_column(Integer)

    # pending | filled | cancelled | expired
    status: Mapped[str] = mapped_column(String(12), server_default="pending")
    filled_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filled_price_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 진입 예약이 묶어둔 현금 — 체결·취소·만료 때 그대로 정산한다.
    reserved_cash_krw: Mapped[int] = mapped_column(BigInteger, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
