from abc import ABC, abstractmethod

from auth.app.dtos.mobile_auth_dto import KakaoIdentityDto


class KakaoIdentityPort(ABC):
    """카카오 액세스 토큰의 신원을 서버가 직접 확인하는 아웃바운드 포트.

    검증 방식(액세스 토큰 조회 / OIDC ID 토큰 서명 검증)을 인터랙터에서 가린다 —
    OIDC로 옮길 때 이 포트의 구현체만 갈아 끼운다.
    """

    @abstractmethod
    async def verify(self, access_token: str) -> KakaoIdentityDto:
        """유효하지 않거나 우리 앱 토큰이 아니면 ValueError."""
        ...
