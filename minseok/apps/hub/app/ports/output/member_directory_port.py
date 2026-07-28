from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.member_directory_dto import MemberInfo, MemberPage, MemberStats, RoleInfo


class MemberDirectoryPort(ABC):
    """허브가 스포크에 위임하는 회원·역할 조회/부여 추상.

    허브는 이 포트(추상)만 알고 어떤 스포크가 구현하는지 모른다(스타 토폴로지 허브 격리).
    구현은 users·RBAC 테이블을 소유한 스포크(auth)가 제공하고, 합성 루트(main.py)에서 주입한다.
    """

    @abstractmethod
    async def list_members(self, search: str | None, limit: int, offset: int) -> MemberPage:
        """회원 목록(이메일/이름 검색, 페이지네이션) + 각자의 role 코드를 반환한다."""
        ...

    @abstractmethod
    async def find_email(self, user_id: int) -> str | None:
        """해당 유저의 이메일 주소를 반환한다(부재·탈퇴 시 None).

        발신 대상을 본인으로 고정하기 위한 조회다 — 수신자는 요청 본문이 아니라 이 값으로 정한다.
        """
        ...

    @abstractmethod
    async def member_stats(self) -> MemberStats:
        """전체 회원 수 + 이번 달 신규 가입 수를 반환한다."""
        ...

    @abstractmethod
    async def list_roles(self) -> list[RoleInfo]:
        """역할 목록과 각 역할의 permission 코드를 반환한다."""
        ...

    @abstractmethod
    async def grant_role(self, user_id: int, role_code: str) -> MemberInfo:
        """역할을 부여하고(멱등) 갱신된 회원 정보를 반환한다. 대상 부재 시 ValueError."""
        ...

    @abstractmethod
    async def revoke_role(self, user_id: int, role_code: str) -> MemberInfo:
        """역할을 회수하고(멱등) 갱신된 회원 정보를 반환한다. 대상 부재 시 ValueError."""
        ...

    @abstractmethod
    async def list_user_permissions(self, user_id: int) -> list[str]:
        """해당 유저가 보유한 permission 코드 목록을 반환한다(비관리자는 빈 리스트)."""
        ...

    @abstractmethod
    async def suspend(self, user_id: int, reason: str) -> MemberInfo:
        """계정 정지(해제 가능) + 리프레시 토큰 전량 폐기. 대상 부재/탈퇴 계정은 ValueError."""
        ...

    @abstractmethod
    async def reinstate(self, user_id: int) -> MemberInfo:
        """정지 해제 — 상태 플래그만 되돌린다(세션은 복원하지 않음, 재로그인 필요)."""
        ...

    @abstractmethod
    async def revoke_sessions(self, user_id: int) -> int:
        """리프레시 토큰 전량 폐기(강제 로그아웃) — 폐기 건수 반환. 대상 부재 시 ValueError."""
        ...

    @abstractmethod
    async def withdraw(self, user_id: int) -> MemberInfo:
        """탈퇴 처리(비가역) — 개인정보 익명화 + 역할 회수 + 토큰 폐기. 이미 탈퇴면 ValueError."""
        ...
