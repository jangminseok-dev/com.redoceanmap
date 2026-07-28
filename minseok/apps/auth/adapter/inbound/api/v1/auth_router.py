from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.adapter.inbound.api.cookie import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from auth.adapter.inbound.api.schemas.auth_schema import (
    LoginRequest,
    RegisterRequest,
    SessionResponse,
)
from auth.app.ports.input.auth_use_case import AuthUseCase
from auth.dependencies.auth_provider import get_auth_use_case
from core.rate_limit import rate_limit

auth_router = APIRouter(prefix="/auth", tags=["auth"])
_optional_bearer = HTTPBearer(auto_error=False)  # 헤더 폴백 — 테스트·도구·비브라우저 클라이언트용

# 무차별 대입·크리덴셜 스터핑 방어 (IP 기준). 정상 사용자는 닿을 수 없는 여유 있는 한도다.
# 가입만 시간 단위인 이유: 오타 재시도가 없고 자동 가입이 스팸·릴레이의 입구이기 때문.
_LOGIN_LIMIT = [rate_limit("login", limit=10, window_seconds=60)]
_REGISTER_LIMIT = [rate_limit("register", limit=5, window_seconds=3600)]
_REFRESH_LIMIT = [rate_limit("refresh", limit=30, window_seconds=60)]


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
    return {"id": user.id, "email": user.email, "name": user.name}
