from pydantic import BaseModel, Field

# 필드명은 앱이 보내는 그대로 camelCase다(www·flutter 공통 규칙 — 경계에서 이름을 바꾸지 않는다).


class MobileKakaoLoginRequest(BaseModel):
    """앱이 보내는 것은 카카오 토큰과 기기 식별자뿐이다.

    프로필(닉네임·이메일)은 받지 않는다 — 클라이언트가 보낸 신원 정보는 신뢰하지 않고,
    서버가 카카오에 직접 확인한 값만 저장한다.
    """

    accessToken: str = Field(min_length=1)
    deviceId: str = Field(min_length=1, max_length=128)


class MobileSessionResponse(BaseModel):
    """모바일은 쿠키를 쓰지 않는다 — 토큰을 본문으로 내린다(웹 SessionResponse와 다른 이유)."""

    accessToken: str
    refreshToken: str
