"""회원 디렉토리 계약 DTO.

허브가 공개하는 앱 간 협력 계약의 일부. auth(스포크)가 채워서 반환하고
admin(스포크)이 소비한다. 원시 값만 담는 순수 도메인 객체다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemberInfo:
    id: int
    # 카카오 모바일 가입은 이메일이 선택 동의라 없을 수 있다(식별자는 users.kakao_id).
    # 계약이 str이면 소비자가 직렬화에서 터진다 — 2026-08-03 어드민 회원목록 500의 원인.
    email: str | None
    name: str
    joined_at: datetime | None  # terms_agreed_at 프록시 — 동의 이력 없는 구유저는 None
    marketing_agreed: bool
    roles: tuple[str, ...]  # role code 목록 (예: ("admin",))
    suspended_at: datetime | None = None  # 정지 시각 (None = 정상)
    deleted_at: datetime | None = None  # 탈퇴 시각 — 개인정보 익명화됨


@dataclass(frozen=True)
class MemberPage:
    total: int
    items: list[MemberInfo]


@dataclass(frozen=True)
class MemberStats:
    total: int
    new_this_month: int  # 이번 달 필수 약관 동의(가입) 수


@dataclass(frozen=True)
class RoleInfo:
    code: str
    name: str
    permissions: tuple[str, ...]  # permission code 목록
