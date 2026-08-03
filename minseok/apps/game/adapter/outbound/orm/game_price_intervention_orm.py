from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GamePriceInterventionOrm(Base):
    """관리자 주가 개입 — 이 게임에서 **저장되는 유일한 시장 사건**.

    주가·뉴스는 전부 `f(에포크, 틱)`으로 유도되므로 저장하지 않는다(game-harness §4-2).
    관리자의 의도만은 난수에서 유도할 수 없어 예외를 둔다. 대신 두 가지로 범위를 좁힌다.

    1. `from_tick`은 **생성 시점의 현재 틱**이다. 그보다 이른 틱에서는 기여가 0이므로
       이미 체결된 체결가·분기 결산·과거 차트가 소급 변조되지 않는다.
    2. **취소·삭제가 없다.** 행을 지우면 그 개입이 걸려 있던 구간의 과거 가격이 통째로
       바뀐다(같은 틱을 다시 물었을 때 값이 달라진다 — §1-A 정면 위반). 개입은 이벤트 창
       `EVENT_WINDOW_TICKS`(게임 5일) 안에서 테이퍼로 저절로 소멸하고, 잘못 넣었으면
       **반대 방향 개입을 하나 더** 넣어 정정한다(현실의 정정 공시와 같은 방식).
    """

    __tablename__ = "game_price_interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch_id: Mapped[int] = mapped_column(Integer, index=True)
    scope: Mapped[str] = mapped_column(String(8))  # symbol | sector | market
    target: Mapped[str] = mapped_column(String(32))  # 종목 코드 · 묶음 업종명 · "" (전체)
    target_name: Mapped[str] = mapped_column(String(32))
    from_tick: Mapped[int] = mapped_column(Integer, index=True)
    shock_pct: Mapped[float] = mapped_column(Float)  # 즉시 충격(%) — 부호가 호재·악재
    drift_pct_per_day: Mapped[float] = mapped_column(Float)
    duration_days: Mapped[int] = mapped_column(Integer)
    headline: Mapped[str] = mapped_column(String(120))  # 유저에게 보이는 문구
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 관리자 메모(비공개)
    # 타입 명시 이유 → game_wallet_orm 참고 (users는 auth 소유)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
