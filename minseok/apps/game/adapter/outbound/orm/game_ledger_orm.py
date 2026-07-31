from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameLedgerOrm(Base):
    """현금 원장 — 지갑 잔고가 변한 모든 사건.

    **이 테이블이 밸런스와 버그를 동시에 잡는 장치다**(game-strategy §6-3).
    현금 증감만 기록하므로 불변식이 단순하다:

        SUM(game_ledger.amount_krw WHERE user_id = ?) == game_wallets.cash_krw

    원장 없이 지갑만 두면 어디서 돈이 새는지 영원히 알 수 없다.
    총자산(현금 + 미청산 포지션 평가액)은 원장이 아니라 조회 시점에 계산한다 —
    미실현 손익은 아직 일어나지 않은 사건이라 원장에 들어갈 자리가 없다.
    """

    __tablename__ = "game_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    game_day: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))  # initial | trade | store | settlement
    amount_krw: Mapped[int] = mapped_column(BigInteger)  # 부호 있는 현금 증감
    ref_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # position | store …
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
