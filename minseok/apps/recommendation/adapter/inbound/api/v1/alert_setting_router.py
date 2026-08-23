"""alert_setting_router.py — 관심 종목 이메일 알림 수신 설정(조회·토글)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import get_current_user_id
from recommendation.adapter.inbound.api.schemas.alert_setting_schema import (
    AlertSettingMyselfResponse,
    AlertSettingResponse,
    AlertSettingSaveRequest,
)
from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft
from recommendation.app.ports.input.alert_setting_use_case import AlertSettingUseCase
from recommendation.dependencies.alert_setting_provider import get_alert_setting_use_case

alert_setting_router = APIRouter(prefix="/alert-settings", tags=["recommendations"])


@alert_setting_router.get("/myself", response_model=AlertSettingMyselfResponse)
async def introduce_myself() -> AlertSettingMyselfResponse:
    return AlertSettingMyselfResponse(
        name="알림 수신 설정",
        description=(
            "관심 종목 이메일 알림의 수신 여부를 관리하는 창구입니다. 설정한 적이 없으면 "
            "수신(켬)이 기본이고, 끄면 알림 스캔이 그 회원의 북마크를 아예 훑지 않습니다. "
            "알림 내용·발송 주기는 여기서 다루지 않습니다(발송은 자동화가 맡습니다)."
        ),
        endpoints=[
            "GET /alert-settings/myself — 이 소개",
            "GET /alert-settings — 내 수신 여부(미설정이면 true)",
            "PUT /alert-settings — 저장 {email_alerts: bool} (재저장 멱등)",
        ],
    )


@alert_setting_router.get("", response_model=AlertSettingResponse)
async def get_my_setting(
    user_id: int = Depends(get_current_user_id),
    use_case: AlertSettingUseCase = Depends(get_alert_setting_use_case),
) -> AlertSettingResponse:
    return AlertSettingResponse(email_alerts=await use_case.get_mine(user_id))


@alert_setting_router.put("", response_model=AlertSettingResponse)
async def save_my_setting(
    payload: AlertSettingSaveRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: AlertSettingUseCase = Depends(get_alert_setting_use_case),
) -> AlertSettingResponse:
    saved = await use_case.save(AlertSettingDraft(
        user_id=user_id, email_alerts=payload.email_alerts,
    ))
    return AlertSettingResponse(email_alerts=saved)
