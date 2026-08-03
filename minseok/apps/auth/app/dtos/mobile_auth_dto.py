from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class KakaoIdentityDto:
    """서버가 카카오에 직접 확인한 신원 — 클라이언트가 보낸 값은 여기에 들어오지 않는다.

    terms_agreed: 카카오싱크 간편가입 동의 화면에서 우리 필수 약관까지 동의된 경우 True.
    """

    kakao_id: int
    email: str | None = None
    nickname: str | None = None
    terms_agreed: bool = False
    marketing_agreed: bool = False


@dataclass(frozen=True)
class MobileLoginCommand:
    """모바일 로그인 요청 — 카카오 액세스 토큰과 기기 식별자만 받는다."""

    access_token: str
    device_id: str
    user_agent: str = ""


@dataclass(frozen=True)
class MobileRefreshSessionDto:
    """저장된 리프레시 세션 — 갱신 때 기기 정보를 새 토큰에 그대로 물려주기 위해 읽는다.

    expires_at은 남은 수명이다. 회전 후 denylist를 언제까지 유지할지가 여기서 정해진다 —
    원래 만료 시각을 넘겨 붙들 이유가 없다(그 시점엔 토큰 자체가 무효다).
    """

    device_id: str
    user_agent: str
    expires_at: datetime


@dataclass(frozen=True)
class MobileSessionDto:
    """모바일 로그인 결과.

    status == "ok"               → access_token·refresh_token 채워짐
    status == "consent_required" → 필수 약관 미동의 신규 유저 (아직 가입 안 됨)
    """

    status: str
    access_token: str | None = None
    refresh_token: str | None = None
