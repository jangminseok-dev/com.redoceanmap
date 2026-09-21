from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.adapter.inbound.api.cookie import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from auth.adapter.inbound.api.schemas.auth_schema import (
    EmailVerifyRequest,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
)
from auth.app.dtos.email_verification_dto import VerifyRequestOutcome
from auth.app.ports.input.auth_use_case import AuthUseCase
from auth.app.ports.input.email_verification_use_case import EmailVerificationUseCase
from auth.dependencies.auth_provider import get_auth_use_case
from auth.dependencies.email_verification_provider import get_email_verification_use_case
from core.rate_limit import rate_limit

auth_router = APIRouter(prefix="/auth", tags=["auth"])
_optional_bearer = HTTPBearer(auto_error=False)  # 헤더 폴백 — 테스트·도구·비브라우저 클라이언트용

# 무차별 대입·크리덴셜 스터핑 방어 (IP 기준). 정상 사용자는 닿을 수 없는 여유 있는 한도다.
# 가입만 시간 단위인 이유: 오타 재시도가 없고 자동 가입이 스팸·릴레이의 입구이기 때문.
_LOGIN_LIMIT = [rate_limit("login", limit=10, window_seconds=60)]
_REGISTER_LIMIT = [rate_limit("register", limit=5, window_seconds=3600)]
_REFRESH_LIMIT = [rate_limit("refresh", limit=30, window_seconds=60)]
# 인증 메일은 "아직 확인 안 된 주소로 가는 메일"이다 — 계정당 제한(도메인 규칙)에 더해 IP로도 묶는다.
_VERIFY_REQUEST_LIMIT = [rate_limit("email-verify-request", limit=10, window_seconds=3600)]
_VERIFY_LIMIT = [rate_limit("email-verify", limit=30, window_seconds=3600)]

# 인증 메일 요청 결과 → (HTTP 상태, 안내 문구). 발송한 경우만 200이다.
_VERIFY_REQUEST_REPLY: dict[VerifyRequestOutcome, tuple[int, str]] = {
    VerifyRequestOutcome.SENT: (200, "인증 메일을 보냈어요. 메일의 링크를 24시간 안에 눌러 주세요."),
    VerifyRequestOutcome.ALREADY_VERIFIED: (200, "이미 인증된 이메일이에요."),
    VerifyRequestOutcome.NO_EMAIL: (409, "이 계정에는 이메일 주소가 없어요."),
    VerifyRequestOutcome.UNDELIVERABLE: (422, "이 주소로는 메일을 보낼 수 없어요."),
    VerifyRequestOutcome.THROTTLED: (429, "인증 메일은 5분에 한 번, 하루 3번까지 보낼 수 있어요. 잠시 뒤에 다시 시도해 주세요."),
}


def _token_from(
    cookie_token: str | None, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """쿠키 우선, Authorization 헤더 폴백(B.3) — 검증부 공통 규칙."""
    return cookie_token or (credentials.credentials if credentials else None)


@auth_router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=_REGISTER_LIMIT,
)
async def register(
    body: RegisterRequest,
    response: Response,
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    try:
        result = await use_case.register(
            body.email,
            body.password,
            body.name,
            terms_agreed=body.terms_agreed,
            marketing_agreed=body.marketing_agreed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return result


@auth_router.post("/login", response_model=SessionResponse, dependencies=_LOGIN_LIMIT)
async def login(
    body: LoginRequest,
    response: Response,
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    try:
        result = await use_case.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return result


@auth_router.post("/refresh", response_model=SessionResponse, dependencies=_REFRESH_LIMIT)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    """리프레시(쿠키 전용) — 회전된 새 쌍을 Set-Cookie로 내린다."""
    token = refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다.")
    try:
        result = await use_case.refresh(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return result


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    """로그아웃(B.2) — 저장 리프레시 폐기 + 두 쿠키 삭제. 멱등."""
    await use_case.logout(refresh_token)
    clear_auth_cookies(response)


@auth_router.get("/tabs")
async def tabs(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    """보이는 탭 키 목록 — 등급(역할) 합집합. 토큰 없음/무효면 기본 등급(basic) 구성."""
    return {"tabs": await use_case.get_tabs(_token_from(access_token, credentials))}


@auth_router.get("/me")
async def me(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    use_case: AuthUseCase = Depends(get_auth_use_case),
):
    token = _token_from(access_token, credentials)
    user = await use_case.get_me(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return {"id": user.id, "email": user.email, "name": user.name,
            "emailVerified": user.email_verified_at is not None}


@auth_router.post("/email/verify-request", dependencies=_VERIFY_REQUEST_LIMIT)
async def request_email_verification(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    use_case: AuthUseCase = Depends(get_auth_use_case),
    verification: EmailVerificationUseCase = Depends(get_email_verification_use_case),
):
    """로그인한 **본인 주소로만** 인증 메일을 보낸다 — 알림 메일을 받기 위한 조건이지 가입·로그인의 관문이 아니다."""
    token = _token_from(access_token, credentials)
    user = await use_case.get_me(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    try:
        outcome = await verification.request(user.id)
    except Exception:
        # 발송 경로(n8n → Gmail) 장애 — 서비스 이용은 그대로 되고 알림 메일 수신만 미뤄진다
        raise HTTPException(status_code=503, detail="지금은 인증 메일을 보낼 수 없어요. 잠시 뒤에 다시 시도해 주세요.")
    code, message = _VERIFY_REQUEST_REPLY[outcome]
    if code >= 400:
        raise HTTPException(status_code=code, detail=message)
    return {"outcome": outcome.value, "message": message}


@auth_router.post("/email/verify", dependencies=_VERIFY_LIMIT)
async def verify_email(
    body: EmailVerifyRequest,
    verification: EmailVerificationUseCase = Depends(get_email_verification_use_case),
):
    """메일 링크의 토큰을 확인한다. 없는·만료된·이미 쓴 토큰은 같은 400 — 어느 쪽인지 알려 주지 않는다."""
    if not await verification.confirm(body.token):
        raise HTTPException(status_code=400, detail="링크가 만료됐거나 이미 사용됐어요. 프로필에서 인증 메일을 다시 받아 주세요.")
    return {"verified": True}
