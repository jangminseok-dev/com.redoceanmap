from pydantic import BaseModel, EmailStr, Field, field_validator

MIN_PASSWORD_LENGTH = 10  # 길이 하나로 간다 — 문자 조합 강제는 예측 가능한 치환만 유도한다(NIST SP 800-63B)
MAX_PASSWORD_BYTES = 72  # bcrypt 하드 한계. 넘기면 bcrypt 5.0이 ValueError → 가입이 500으로 터진다


def _within_bcrypt_limit(value: str) -> str:
    # 문자 수가 아니라 UTF-8 바이트 수다 — 한글은 1자 3바이트라 24자만 넘어도 한계에 닿는다.
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"비밀번호는 UTF-8 기준 {MAX_PASSWORD_BYTES}바이트를 넘을 수 없습니다.")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    name: str
    terms_agreed: bool  # 필수 — 이용약관·개인정보 수집 동의 (false면 400)
    marketing_agreed: bool = False  # 선택 — 마케팅 정보 수신 동의

    _check_password = field_validator("password")(_within_bcrypt_limit)


class LoginRequest(BaseModel):
    """검증은 값이 만들어지는 가입 쪽에만 건다 — 여기서 조이면 기존 계정이 잠긴다.

    이메일은 조회 키일 뿐이라 형식 검증의 이득이 없고(EmailStr은 `.local` 등도 거부한다),
    최소 길이는 정책 도입 전 가입자를 로그인 불가로 만든다. bcrypt 바이트 상한만 공유한다 —
    가입에서 막히므로 그런 비밀번호는 존재할 수 없고, 검증 단계의 ValueError → 500을 막는다.
    """

    email: str
    password: str

    _check_password = field_validator("password")(_within_bcrypt_limit)


class SessionResponse(BaseModel):
    """인증 성공 응답 — 토큰은 본문이 아니라 httpOnly Set-Cookie로만 내려간다(BFF 규칙 2)."""

    name: str
    email: str
