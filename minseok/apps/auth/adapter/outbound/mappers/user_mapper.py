from auth.adapter.outbound.orm.user_orm import UserOrm
from auth.domain.entities.user_entity import User


class UserMapper:
    """UserOrm(영속성) ↔ User(도메인) 변환을 담당한다."""

    @staticmethod
    def to_entity(orm: UserOrm) -> User:
        return User(
            id=orm.id,
            email=orm.email,
            password_hash=orm.password_hash,
            name=orm.name,
            kakao_id=orm.kakao_id,
            last_login_at=orm.last_login_at,
            terms_agreed_at=orm.terms_agreed_at,
            marketing_agreed=orm.marketing_agreed,
            suspended_at=orm.suspended_at,
            suspended_reason=orm.suspended_reason,
            deleted_at=orm.deleted_at,
            email_verified_at=orm.email_verified_at,
        )
