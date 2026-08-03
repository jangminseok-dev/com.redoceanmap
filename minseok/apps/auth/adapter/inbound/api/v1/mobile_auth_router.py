from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.adapter.inbound.api.schemas.mobile_auth_schema import (
    MobileConsentRequest,
    MobileKakaoLoginRequest,
    MobileRefreshRequest,
    MobileSessionResponse,
)
from auth.app.dtos.mobile_auth_dto import (
    MobileConsentCommand,
    MobileLoginCommand,
    MobileSessionDto,
)
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.dependencies.mobile_auth_provider import get_mobile_auth_use_case
from core.rate_limit import rate_limit

# 경로 자체를 플랫폼으로 가른다 — 공용 엔드포인트에 platform 파라미터를 받지 않는다.
mobile_auth_router = APIRouter(prefix="/auth/mobile", tags=["auth"])

# 탈취한 카카오 토큰 대입을 늦춘다. 정상 앱은 실행당 1회라 닿을 수 없는 한도다.
_LOGIN_LIMIT = [rate_limit("mobile_kakao", limit=10, window_seconds=60)]
# 갱신은 액세스 토큰(30분)이 죽을 때마다라 로그인보다 잦다 — 웹 refresh와 같은 한도를 쓴다.
_REFRESH_LIMIT = [rate_limit("mobile_refresh", limit=30, window_seconds=60)]
# 동의는 가입당 1회다. 서명된 토큰이 있어야 통과하므로 로그인과 같은 한도면 충분하다.
_CONSENT_LIMIT = [rate_limit("mobile_consent", limit=10, window_seconds=60)]


def _to_response(result: MobileSessionDto) -> MobileSessionResponse:
    """status에 따라 채워지는 필드가 다르다 — 판단은 유스케이스가 하고 여기선 옮기기만 한다."""
    return MobileSessionResponse(
        status=result.status,
        accessToken=result.access_token,
        refreshToken=result.refresh_token,
        consentToken=result.consent_token,
    )


@mobile_auth_router.post(
    "/kakao", response_model=MobileSessionResponse, dependencies=_LOGIN_LIMIT
)
async def login_with_kakao(
    body: MobileKakaoLoginRequest,
    request: Request,
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    """카카오 로그인(모바일) — 앱이 받은 카카오 액세스 토큰을 본문으로만 받는다.

    쿼리 파라미터로 받지 않는다(액세스 로그에 남는다). 응답은 자체 JWT이며,
    리프레시 토큰은 Redis 모바일 DB(db 1)에 함께 적재된다.

    필수 약관 동의가 확인되지 않은 신규 유저에게는 `status="consent_required"`와
    `consentToken`을 200으로 내린다 — 실패가 아니라 가입 절차의 한 단계다.
    """
    try:
        result = await use_case.login_with_kakao(
            MobileLoginCommand(
                access_token=body.accessToken,
                device_id=body.deviceId,
                user_agent=request.headers.get("User-Agent", ""),
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return _to_response(result)


@mobile_auth_router.post(
    "/consent", response_model=MobileSessionResponse, dependencies=_CONSENT_LIMIT
)
async def complete_consent(
    body: MobileConsentRequest,
    request: Request,
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    """동의 완료 → 가입(모바일) — `/kakao`가 내준 consentToken으로 계정을 만든다.

    카카오싱크(비즈니스 앱)를 못 쓰는 동안 필수 약관 동의를 우리 앱 화면에서 받기 위한 경로다.
    동의 시각은 이 요청이 도달한 시점으로 기록된다.
    """
    try:
        result = await use_case.complete_consent(
            MobileConsentCommand(
                consent_token=body.consentToken,
                marketing_agreed=body.marketingAgreed,
                device_id=body.deviceId,
                user_agent=request.headers.get("User-Agent", ""),
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return _to_response(result)


@mobile_auth_router.post(
    "/refresh", response_model=MobileSessionResponse, dependencies=_REFRESH_LIMIT
)
async def refresh(
    body: MobileRefreshRequest,
    use_case: MobileAuthUseCase = Depends(get_mobile_auth_use_case),
):
    """세션 갱신(모바일) — 앱 부팅 시 세션 복원 경로다.

    쿠키를 쓰지 않으므로 리프레시 토큰을 본문으로 받고 본문으로 돌려준다(웹 `/auth/refresh`와
    다른 점). 한 번 쓴 토큰은 즉시 폐기되고 새 쌍이 나온다 — 앱은 응답의 refreshToken으로
    저장값을 반드시 덮어써야 한다.
    """
    try:
        result = await use_case.refresh(body.refreshToken)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return _to_response(result)
