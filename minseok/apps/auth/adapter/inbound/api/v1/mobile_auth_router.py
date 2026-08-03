from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.adapter.inbound.api.schemas.mobile_auth_schema import (
    MobileKakaoLoginRequest,
    MobileSessionResponse,
)
from auth.app.dtos.mobile_auth_dto import MobileLoginCommand
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.dependencies.mobile_auth_provider import get_mobile_auth_use_case
from core.rate_limit import rate_limit

# 경로 자체를 플랫폼으로 가른다 — 공용 엔드포인트에 platform 파라미터를 받지 않는다.
mobile_auth_router = APIRouter(prefix="/auth/mobile", tags=["auth"])

# 탈취한 카카오 토큰 대입을 늦춘다. 정상 앱은 실행당 1회라 닿을 수 없는 한도다.
_LOGIN_LIMIT = [rate_limit("mobile_kakao", limit=10, window_seconds=60)]


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
    if result.status == "consent_required":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="필수 약관 동의가 필요합니다. 카카오 로그인 동의 화면에서 필수 항목에 동의해 주세요.",
        )
    return MobileSessionResponse(
        accessToken=result.access_token, refreshToken=result.refresh_token
    )
