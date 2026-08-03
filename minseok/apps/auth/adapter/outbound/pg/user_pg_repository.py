from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.mappers.user_mapper import UserMapper
from auth.adapter.outbound.orm.user_orm import UserOrm
from auth.app.ports.output.user_repository import UserRepository
from auth.domain.entities.user_entity import User


class UserPgRepository(UserRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserOrm).where(UserOrm.email == email))
        orm = result.scalar_one_or_none()
        return UserMapper.to_entity(orm) if orm is not None else None

    async def find_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(UserOrm).where(UserOrm.id == user_id))
        orm = result.scalar_one_or_none()
        return UserMapper.to_entity(orm) if orm is not None else None

    async def find_by_kakao_id(self, kakao_id: int) -> User | None:
        result = await self._session.execute(select(UserOrm).where(UserOrm.kakao_id == kakao_id))
        orm = result.scalar_one_or_none()
        return UserMapper.to_entity(orm) if orm is not None else None

    async def create(
        self,
        email: str | None,
        password_hash: str,
        name: str,
        terms_agreed_at: datetime | None = None,
        marketing_agreed: bool = False,
        kakao_id: int | None = None,
    ) -> User:
        result = await self._session.execute(
            insert(UserOrm)
            .values(
                email=email,
                password_hash=password_hash,
                name=name,
                terms_agreed_at=terms_agreed_at,
                marketing_agreed=marketing_agreed,
                kakao_id=kakao_id,
            )
            .returning(UserOrm)
        )
        await self._session.commit()
        return UserMapper.to_entity(result.scalar_one())

    async def touch_last_login(self, user_id: int) -> None:
        await self._session.execute(
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        await self._session.commit()
