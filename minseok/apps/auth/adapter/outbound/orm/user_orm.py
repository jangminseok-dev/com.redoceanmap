from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class UserOrm(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 카카오는 이메일 제공이 선택 동의라 없을 수 있다 — 식별자는 kakao_id가 맡는다.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    kakao_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 약관 동의 증빙 — 필수 약관(이용약관·개인정보) 동의 시각. 기존 유저는 NULL(소급 없음).
    terms_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marketing_agreed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # 운영 제재 — 정지(해제 가능)와 탈퇴(익명화, 비가역). NULL = 정상.
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 이메일 인증 시각 — NULL = 미인증. 알림 메일은 인증된 주소로만 나간다(가입·로그인은 막지 않는다).
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
