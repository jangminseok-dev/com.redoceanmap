from __future__ import annotations

from abc import ABC, abstractmethod

from auth.app.dtos.mobile_gatekeeper_dto import (
    MobileGatekeeperQuery,
    MobileGatekeeperResponse,
)


class MobileGatekeeperUseCase(ABC):
    """모바일 인증 (auth/mobile) 유스케이스 — 앱 전용 로그인 경로의 자기소개."""

    @abstractmethod
    async def introduce_myself(
        self, query: MobileGatekeeperQuery
    ) -> MobileGatekeeperResponse:
        """모바일 인증의 자기소개 메소드."""
        ...
