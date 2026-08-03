from pydantic import BaseModel, Field

# 필드명은 앱이 보내는 그대로 camelCase다(www·flutter 공통 규칙 — 경계에서 이름을 바꾸지 않는다).


class MobileKakaoLoginRequest(BaseModel):
    """앱이 보내는 것은 카카오 토큰과 기기 식별자뿐이다.

    프로필(닉네임·이메일)은 받지 않는다 — 클라이언트가 보낸 신원 정보는 신뢰하지 않고,
    서버가 카카오에 직접 확인한 값만 저장한다.
    """

    accessToken: str = Field(min_length=1)
    deviceId: str = Field(min_length=1, max_length=128)


class MobileRefreshRequest(BaseModel):
    """갱신에 필요한 것은 리프레시 토큰뿐이다.

    deviceId를 다시 받지 않는다 — 기기 정보는 발급 때 저장한 값을 그대로 물려준다.
    클라이언트가 갱신 시점에 바꿔 보낼 수 있으면 기기 목록이 위조된다.
    """

    refreshToken: str = Field(min_length=1, max_length=256)


class MobileConsentRequest(BaseModel):
    """앱 동의 화면에서 필수 약관을 받은 뒤 보내는 가입 완료 요청.

    카카오 회원번호를 받지 않는다 — 신원은 서버가 서명한 consentToken 안에만 있다.
    """

    consentToken: str = Field(min_length=1)
    marketingAgreed: bool = False
    deviceId: str = Field(min_length=1, max_length=128)


class MobileSessionResponse(BaseModel):
    """모바일은 쿠키를 쓰지 않는다 — 토큰을 본문으로 내린다(웹 SessionResponse와 다른 이유).

    status == "ok"               → accessToken·refreshToken
    status == "consent_required" → consentToken (아직 계정이 없다. 앱은 동의 화면으로 분기한다)

    동의 필요를 오류(403)가 아니라 200으로 내리는 이유: 실패가 아니라 절차의 한 단계이고,
    오류 본문에 다음 단계용 토큰을 실어 보내는 형태를 피하기 위해서다.
    """

    status: str
    accessToken: str | None = None
    refreshToken: str | None = None
    consentToken: str | None = None
