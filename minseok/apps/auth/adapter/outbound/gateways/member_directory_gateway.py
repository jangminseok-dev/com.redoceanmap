from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.orm.rbac_orm import (
    PermissionOrm,
    RolePermissionOrm,
    RoleOrm,
    UserRoleOrm,
)
from auth.adapter.outbound.orm.user_orm import UserOrm
from auth.app.ports.output.refresh_token_repository import RefreshTokenRepository
from hub.app.dtos.member_directory_dto import MemberInfo, MemberPage, MemberStats, RoleInfo
from hub.app.ports.output.member_directory_port import MemberDirectoryPort


class MemberDirectoryGateway(MemberDirectoryPort):
    """허브의 MemberDirectoryPort를 auth(스포크)가 구현한다.

    스포크 → 허브 추상에만 의존(스타 토폴로지 허용). users·RBAC 4테이블을 조회/갱신해
    허브 계약 DTO로 반환한다. 제재(정지/탈퇴/세션 폐기)는 리프레시 저장소와 협력한다.
    """

    def __init__(self, session: AsyncSession, refresh_repository: RefreshTokenRepository) -> None:
        self._session = session
        self._refresh = refresh_repository

    async def list_members(self, search: str | None, limit: int, offset: int) -> MemberPage:
        base = select(UserOrm)
        if search:
            pattern = f"%{search}%"
            base = base.where(or_(UserOrm.email.ilike(pattern), UserOrm.name.ilike(pattern)))

        total = (
            await self._session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar() or 0
        users = (
            await self._session.execute(base.order_by(UserOrm.id.desc()).limit(limit).offset(offset))
        ).scalars().all()

        roles_map = await self._roles_by_user([u.id for u in users])
        return MemberPage(total=total, items=[self._to_info(u, roles_map) for u in users])

    async def find_email(self, user_id: int) -> str | None:
        return (
            await self._session.execute(
                select(UserOrm.email).where(
                    UserOrm.id == user_id, UserOrm.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()

    async def member_stats(self) -> MemberStats:
        total = (await self._session.execute(select(func.count(UserOrm.id)))).scalar() or 0
        new_this_month = (
            await self._session.execute(
                select(func.count(UserOrm.id)).where(
                    UserOrm.terms_agreed_at >= func.date_trunc("month", func.now())
                )
            )
        ).scalar() or 0
        return MemberStats(total=total, new_this_month=new_this_month)

    async def list_roles(self) -> list[RoleInfo]:
        rows = (
            await self._session.execute(
                select(RoleOrm.code, RoleOrm.name, PermissionOrm.code.label("perm"))
                .outerjoin(RolePermissionOrm, RolePermissionOrm.role_id == RoleOrm.id)
                .outerjoin(PermissionOrm, PermissionOrm.id == RolePermissionOrm.permission_id)
                .order_by(RoleOrm.id)
            )
        ).all()
        grouped: dict[str, tuple[str, list[str]]] = {}
        for r in rows:
            grouped.setdefault(r.code, (r.name, []))
            if r.perm:
                grouped[r.code][1].append(r.perm)
        return [
            RoleInfo(code=code, name=name, permissions=tuple(perms))
            for code, (name, perms) in grouped.items()
        ]

    async def grant_role(self, user_id: int, role_code: str) -> MemberInfo:
        user, role_id = await self._resolve(user_id, role_code)
        if user.deleted_at is not None:
            raise ValueError("탈퇴한 계정에는 역할을 부여할 수 없습니다.")
        exists = (
            await self._session.execute(
                select(UserRoleOrm.id).where(
                    UserRoleOrm.user_id == user_id, UserRoleOrm.role_id == role_id
                )
            )
        ).first()
        if not exists:
            self._session.add(UserRoleOrm(user_id=user_id, role_id=role_id))
            await self._session.commit()
        roles_map = await self._roles_by_user([user_id])
        return self._to_info(user, roles_map)

    async def revoke_role(self, user_id: int, role_code: str) -> MemberInfo:
        user, role_id = await self._resolve(user_id, role_code)
        await self._session.execute(
            delete(UserRoleOrm).where(
                UserRoleOrm.user_id == user_id, UserRoleOrm.role_id == role_id
            )
        )
        await self._session.commit()
        roles_map = await self._roles_by_user([user_id])
        return self._to_info(user, roles_map)

    async def list_user_permissions(self, user_id: int) -> list[str]:
        rows = (
            await self._session.execute(
                select(PermissionOrm.code)
                .join(RolePermissionOrm, RolePermissionOrm.permission_id == PermissionOrm.id)
                .join(UserRoleOrm, UserRoleOrm.role_id == RolePermissionOrm.role_id)
                .where(UserRoleOrm.user_id == user_id)
                .distinct()
            )
        ).scalars().all()
        return list(rows)

    async def suspend(self, user_id: int, reason: str) -> MemberInfo:
        user = await self._get_user(user_id)
        if user.deleted_at is not None:
            raise ValueError("탈퇴한 계정은 정지할 수 없습니다.")
        await self._session.execute(
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(suspended_at=datetime.now(timezone.utc), suspended_reason=reason or None)
        )
        await self._session.commit()
        await self._refresh.delete_all_for_user(user_id)  # 강제 로그아웃
        return await self._refreshed_info(user_id)

    async def reinstate(self, user_id: int) -> MemberInfo:
        await self._get_user(user_id)
        await self._session.execute(
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(suspended_at=None, suspended_reason=None)
        )
        await self._session.commit()
        # 정지 중 순단/경합으로 살아남았을 수 있는 잔존 토큰을 마저 폐기한다 —
        # "해제는 세션을 복원하지 않고 재로그인"이라는 계약을 보장(멱등·저비용).
        await self._refresh.delete_all_for_user(user_id)
        return await self._refreshed_info(user_id)

    async def revoke_sessions(self, user_id: int) -> int:
        await self._get_user(user_id)
        return await self._refresh.delete_all_for_user(user_id)

    async def withdraw(self, user_id: int) -> MemberInfo:
        user = await self._get_user(user_id)
        if user.deleted_at is not None:
            raise ValueError("이미 탈퇴 처리된 계정입니다.")
        # 개인정보 파기 원칙 — 식별 정보를 익명화하고 로그인 수단을 무효화한다(비가역).
        # 이메일에 랜덤 토큰을 섞는다 — 예측 가능한 주소(deleted-{id})를 공격자가
        # /auth/register로 선점해 탈퇴 UPDATE를 unique 충돌(500)로 막는 것을 방지.
        anon_email = f"deleted-{user_id}-{secrets.token_hex(4)}@removed.local"
        await self._session.execute(
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(
                email=anon_email,
                name="탈퇴회원",
                password_hash="!",
                marketing_agreed=False,
                suspended_at=None,
                suspended_reason=None,
                deleted_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(delete(UserRoleOrm).where(UserRoleOrm.user_id == user_id))
        await self._session.commit()
        await self._refresh.delete_all_for_user(user_id)
        return await self._refreshed_info(user_id)

    async def _get_user(self, user_id: int) -> UserOrm:
        user = (
            await self._session.execute(select(UserOrm).where(UserOrm.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise ValueError(f"유저가 없습니다: id={user_id}")
        return user

    async def _refreshed_info(self, user_id: int) -> MemberInfo:
        user = await self._get_user(user_id)
        roles_map = await self._roles_by_user([user_id])
        return self._to_info(user, roles_map)

    async def _resolve(self, user_id: int, role_code: str) -> tuple[UserOrm, int]:
        user = await self._get_user(user_id)
        role_id = (
            await self._session.execute(select(RoleOrm.id).where(RoleOrm.code == role_code))
        ).scalar_one_or_none()
        if role_id is None:
            raise ValueError(f"역할이 없습니다: {role_code}")
        return user, role_id

    async def _roles_by_user(self, user_ids: list[int]) -> dict[int, list[str]]:
        if not user_ids:
            return {}
        rows = (
            await self._session.execute(
                select(UserRoleOrm.user_id, RoleOrm.code)
                .join(RoleOrm, RoleOrm.id == UserRoleOrm.role_id)
                .where(UserRoleOrm.user_id.in_(user_ids))
            )
        ).all()
        result: dict[int, list[str]] = {}
        for uid, code in rows:
            result.setdefault(uid, []).append(code)
        return result

    @staticmethod
    def _to_info(user: UserOrm, roles_map: dict[int, list[str]]) -> MemberInfo:
        return MemberInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            joined_at=user.terms_agreed_at,
            marketing_agreed=user.marketing_agreed,
            roles=tuple(roles_map.get(user.id, [])),
            suspended_at=user.suspended_at,
            deleted_at=user.deleted_at,
        )
