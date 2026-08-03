from __future__ import annotations

from admin.app.dtos.member_dto import (
    MemberActionCommand,
    MemberActionResponse,
    MemberListQuery,
    MemberListResponse,
    RoleChangeCommand,
    RoleChangeResponse,
    RoleListResponse,
    SessionRevokeResponse,
    SuspendCommand,
)
from admin.app.ports.input.member_use_case import MemberUseCase
from admin.app.ports.output.audit_log_port import AuditLogPort
from hub.app.dtos.member_directory_dto import MemberInfo
from hub.app.ports.output.member_directory_port import MemberDirectoryPort

MAX_LIMIT = 100


class MemberInteractor(MemberUseCase):
    """어드민 회원 관리 대장 — 허브 MemberDirectoryPort에 위임하고 변경 행위를 감사 기록한다."""

    def __init__(self, members: MemberDirectoryPort, audit: AuditLogPort) -> None:
        self._members = members
        self._audit = audit

    async def list_members(self, query: MemberListQuery) -> MemberListResponse:
        limit = min(max(query.limit, 1), MAX_LIMIT)
        offset = max(query.offset, 0)
        page = await self._members.list_members(search=query.search, limit=limit, offset=offset)
        return MemberListResponse(page=page)

    async def list_roles(self) -> RoleListResponse:
        return RoleListResponse(roles=await self._members.list_roles())

    @staticmethod
    def _label(member: MemberInfo) -> str:
        """감사 기록에 남길 회원 표기 — 이메일 없는 카카오 가입자는 이름으로 대신한다."""
        return member.email or f"{member.name}(이메일 없음)"

    async def grant_role(self, command: RoleChangeCommand) -> RoleChangeResponse:
        member = await self._members.grant_role(command.user_id, command.role_code)
        await self._audit.write(
            actor_id=command.actor_id,
            action="role.grant",
            detail=f"user={command.user_id}({self._label(member)}) role={command.role_code}",
        )
        return RoleChangeResponse(member=member)

    async def revoke_role(self, command: RoleChangeCommand) -> RoleChangeResponse:
        member = await self._members.revoke_role(command.user_id, command.role_code)
        await self._audit.write(
            actor_id=command.actor_id,
            action="role.revoke",
            detail=f"user={command.user_id}({self._label(member)}) role={command.role_code}",
        )
        return RoleChangeResponse(member=member)

    async def suspend(self, command: SuspendCommand) -> MemberActionResponse:
        if command.actor_id == command.user_id:
            raise ValueError("자기 자신은 정지할 수 없습니다.")  # 콘솔 잠금 방지
        member = await self._members.suspend(command.user_id, command.reason)
        await self._audit.write(
            actor_id=command.actor_id,
            action="member.suspend",
            detail=f"user={command.user_id}({self._label(member)}) reason={command.reason or '-'}",
        )
        return MemberActionResponse(member=member)

    async def reinstate(self, command: MemberActionCommand) -> MemberActionResponse:
        member = await self._members.reinstate(command.user_id)
        await self._audit.write(
            actor_id=command.actor_id,
            action="member.reinstate",
            detail=f"user={command.user_id}({self._label(member)})",
        )
        return MemberActionResponse(member=member)

    async def revoke_sessions(self, command: MemberActionCommand) -> SessionRevokeResponse:
        revoked = await self._members.revoke_sessions(command.user_id)
        await self._audit.write(
            actor_id=command.actor_id,
            action="member.sessions.revoke",
            detail=f"user={command.user_id} revoked={revoked}",
        )
        return SessionRevokeResponse(revoked=revoked)

    async def withdraw(self, command: MemberActionCommand) -> MemberActionResponse:
        if command.actor_id == command.user_id:
            raise ValueError("자기 자신은 탈퇴 처리할 수 없습니다. 다른 관리자에게 요청하세요.")
        member = await self._members.withdraw(command.user_id)
        await self._audit.write(
            actor_id=command.actor_id,
            action="member.withdraw",
            detail=f"user={command.user_id} (개인정보 익명화 완료)",
        )
        return MemberActionResponse(member=member)
