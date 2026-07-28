"""langchain_session_orm.py — 랭체인 대화 세션 테이블.

허브가 ORM을 갖는 첫 예외다. 이 대화 이력은 앱 간 협력 계약이 아니라 허브가 직접 소유·구현하는
기능(비전과 같은 성격)이라 스포크에 위임할 자리가 없다. chat 스포크의 `conversations`와 분리한
이유는 소유 앱이 다르고(허브 격리), 턴마다 시멘틱 분류 결과를 함께 남기기 때문이다.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class LangchainSessionOrm(Base):
    __tablename__ = "langchain_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 소유자 — auth 스포크의 users를 FK로 참조하지 않는다(앱 간 DB 결합 회피). 익명은 NULL.
    user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LangchainTurnOrm(Base):
    __tablename__ = "langchain_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("langchain_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    # 그 턴을 만든 시멘틱 분류 결과 — 분기별 품질을 사후에 갈라 보기 위한 관찰 컬럼
    destination: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
