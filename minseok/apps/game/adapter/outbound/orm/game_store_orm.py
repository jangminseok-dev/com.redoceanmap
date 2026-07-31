from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GameStoreOrm(Base):
    """유저가 세운 가게 1곳.

    `profile_snapshot`은 **market 실데이터의 스냅샷**이다. 게임이 계산한 값이 아니라
    창업 시점에 읽은 외부 사실이라 저장한다(체결가를 저장하는 것과 같은 성격,
    game-harness §4-2). 기준 분기가 에포크에 박혀 있어(§1-5) 시즌 내내 값이 같으므로
    재조회해도 결과는 동일하다 — 저장하는 이유는 일일 시뮬이 market DB를 왕복하지
    않게 하려는 것이다.

    담는 것: 적합도, 점포당 월매출, 객단가, 임대료 입지계수, 요일·시간대·성별·연령 분포,
    상권명·업종명.
    """

    __tablename__ = "game_stores"
    __table_args__ = (Index("ix_game_stores_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    trdar_code: Mapped[int] = mapped_column(Integer, index=True)
    service_code: Mapped[str] = mapped_column(String(16))

    opened_game_day: Mapped[int] = mapped_column(Integer)
    closed_game_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16))  # open | suspended | closed

    store_scale: Mapped[float] = mapped_column(Float)  # 0.02~1.00 — 상권 평균 점포 대비
    deposit_krw: Mapped[int] = mapped_column(BigInteger)  # 폐업 시 회수된다
    interior_krw: Mapped[int] = mapped_column(BigInteger)  # 회수되지 않는다

    profile_snapshot: Mapped[dict] = mapped_column(JSONB)
    settled_through_day: Mapped[int] = mapped_column(Integer, default=0)  # 분기 결산 앵커(8단계)

    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
