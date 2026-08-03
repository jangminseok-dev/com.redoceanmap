from abc import ABC, abstractmethod

from auth.app.dtos.mobile_auth_dto import (
    MobileConsentCommand,
    MobileLoginCommand,
    MobileSessionDto,
)


class MobileAuthUseCase(ABC):

    @abstractmethod
    async def login_with_kakao(self, command: MobileLoginCommand) -> MobileSessionDto:
        """카카오 액세스 토큰으로 로그인 — 신원 확인은 서버가 카카오에 직접 한다. 실패 시 ValueError."""
        ...

    @abstractmethod
    async def complete_consent(self, command: MobileConsentCommand) -> MobileSessionDto:
        """앱 동의 화면을 마친 신규 유저를 가입시키고 세션을 발급한다. 실패 시 ValueError."""
        ...

    @abstractmethod
    async def refresh(self, refresh_token: str) -> MobileSessionDto:
        """리프레시 토큰 회전 — 쓴 토큰은 즉시 폐기하고 새 쌍을 발급한다. 실패 시 ValueError."""
        ...
