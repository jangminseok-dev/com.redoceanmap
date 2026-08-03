from abc import ABC, abstractmethod

from auth.app.dtos.mobile_auth_dto import MobileLoginCommand, MobileSessionDto


class MobileAuthUseCase(ABC):

    @abstractmethod
    async def login_with_kakao(self, command: MobileLoginCommand) -> MobileSessionDto:
        """카카오 액세스 토큰으로 로그인 — 신원 확인은 서버가 카카오에 직접 한다. 실패 시 ValueError."""
        ...
