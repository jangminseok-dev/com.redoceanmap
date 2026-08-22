from __future__ import annotations

from abc import ABC, abstractmethod


class MemberContactPort(ABC):
    """회원 연락처(이메일) 조회 계약 — 허브 bookmark_alert(소비)와 auth(구현)를 잇는다.

    MemberDirectoryPort(회원 관리·RBAC)와 별개인 발송 목적 전용 계약(Record ↔ Directory
    분리 선례). 정지·탈퇴 회원과 이메일 없는 계정은 결과에서 빠진다 — 발송 대상이 아니다.
    """

    @abstractmethod
    async def emails_by_ids(self, user_ids: list[int]) -> dict[int, str]:
        """user_id → 이메일. 발송 불가 회원(정지·탈퇴·이메일 없음)은 키 자체가 없다."""
        ...
