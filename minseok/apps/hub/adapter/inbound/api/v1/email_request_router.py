"""email_request_router.py — 이메일 발송 요청 인바운드 어댑터 (액터: 사용자/프론트)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from hub.adapter.inbound.api.schemas.email_request_schema import (
    EmailRequestResultSchema,
    EmailRequestSchema,
)
from hub.app.dtos.email_request_dto import EmailRequestCommand
from hub.app.ports.input.email_request_use_case import EmailRequestUseCase
from hub.dependencies.email_request_provider import get_email_request_use_case

logger = logging.getLogger(__name__)

email_request_router = APIRouter(prefix="/email", tags=["hub-email"])


@email_request_router.post("/request", response_model=EmailRequestResultSchema)
async def request_email(
    schema: EmailRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: EmailRequestUseCase = Depends(get_email_request_use_case),
) -> EmailRequestResultSchema:
    """수신자는 받지 않는다 — 로그인 계정 이메일로만 발송한다(오픈 릴레이 차단)."""
    logger.info("[hub/email/request] requester=%s", user_id)
    try:
        result = await use_case.request(
            EmailRequestCommand(requester_id=user_id, content=schema.content)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EmailRequestResultSchema(status=result.status, detail=result.detail)
