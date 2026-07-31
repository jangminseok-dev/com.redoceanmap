from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameWalletOrm(Base):
    """유저별 게임 지갑 — 투자와 창업이 공유하는 단일 현금 잔고.

    `epoch_id`가 현재 시즌과 다르면 지난 시즌 기록이라 읽기 전용이다(game-harness §1-4).
    주가·이벤트와 달리 지갑은 **유저 행위의 결과**라 저장한다(§4-2).
    """

    __tablename__ = "game_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입을 명시한다 — `users`는 auth 소유라 game만 로드하면 FK가 타입을 못 찾는다
    # (auth를 import하면 해결되지만 그건 스포크 직접 참조라 계약 위반이다).
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    cash_krw: Mapped[int] = mapped_column(BigInteger)
    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
    rule_version: Mapped[str] = mapped_column(String(16))
