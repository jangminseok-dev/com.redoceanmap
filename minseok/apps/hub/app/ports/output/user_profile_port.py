from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.user_profile_dto import UserProfileSummary


class UserProfilePort(ABC):
    """허브가 스포크에 위임하는 사용자 프로파일 조회 추상.

    허브는 이 포트(추상)만 알고 어떤 스포크가 구현하는지 모른다(스타 토폴로지 허브 격리).
    구현은 스포크(recommendation)가 제공하고, 합성 루트(main.py)에서 주입한다.
    """

    @abstractmethod
    async def get_profile(self, user_id: int) -> UserProfileSummary | None:
        """프로파일 요약 — 미작성 사용자는 None(오류 아님, 소비자는 주입 생략)."""
        ...
