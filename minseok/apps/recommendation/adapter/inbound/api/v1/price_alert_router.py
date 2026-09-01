"""price_alert_router.py — 가격 도달 알림 조건(손절·익절선) 등록·조회·삭제.

시그널 대개편 [6]: 방향 예측이 아니라 **사용자가 직접 정한 가격의 도달 사실 통지**다.
도달 판정·발송 조립은 허브 스캔(/automation/price-alerts)이, 실제 발송은 n8n이 맡는다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from core.security import get_current_user_id
from recommendation.adapter.inbound.api.schemas.price_alert_schema import (
    PriceAlertCreateRequest,
    PriceAlertListResponse,
    PriceAlertMyselfResponse,
    PriceAlertResponse,
)
from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert
from recommendation.app.ports.input.price_alert_use_case import PriceAlertUseCase
from recommendation.app.use_cases.price_alert_interactor import (
    MAX_ACTIVE_ALERTS,
    PriceAlertLimitError,
)
from recommendation.dependencies.price_alert_provider import get_price_alert_use_case

price_alert_router = APIRouter(prefix="/price-alerts", tags=["recommendations"])


def _to_schema(a: StoredPriceAlert) -> PriceAlertResponse:
    return PriceAlertResponse(
        id=a.id, ticker=a.ticker, target_price=a.target_price, direction=a.direction,
        active=a.active, triggered_at=a.triggered_at, created_at=a.created_at,
    )


@price_alert_router.get("/myself", response_model=PriceAlertMyselfResponse)
async def introduce_myself() -> PriceAlertMyselfResponse:
    return PriceAlertMyselfResponse(
        name="가격 도달 알림 조건",
        description=(
            "회원이 직접 정한 가격 조건(손절·익절선)을 보관하는 창구입니다. 조건에 도달하면 "
            "1회 통지 후 자동 비활성화됩니다(재알림은 재등록). 가격 도달 판정과 발송은 "
            "자동화 스캔이 맡고, 여기는 조건 관리만 합니다. 매매 지시·방향 예측은 하지 "
            "않습니다 — 사용자가 정한 가격의 도달 '사실'만 다룹니다."
        ),
        endpoints=[
            "GET /price-alerts/myself — 이 소개",
            f"GET /price-alerts — 내 조건 목록(활성 상한 {MAX_ACTIVE_ALERTS}개)",
            "POST /price-alerts — 등록 {ticker, target_price, direction: above|below}",
            "DELETE /price-alerts/{id} — 삭제(본인 것만)",
        ],
    )


@price_alert_router.get("", response_model=PriceAlertListResponse)
async def list_my_alerts(
    user_id: int = Depends(get_current_user_id),
    use_case: PriceAlertUseCase = Depends(get_price_alert_use_case),
) -> PriceAlertListResponse:
    alerts = await use_case.list_mine(user_id)
    return PriceAlertListResponse(
        alerts=[_to_schema(a) for a in alerts], max_active=MAX_ACTIVE_ALERTS,
    )


@price_alert_router.post("", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: PriceAlertCreateRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: PriceAlertUseCase = Depends(get_price_alert_use_case),
) -> PriceAlertResponse:
    try:
        stored = await use_case.create(PriceAlertDraft(
            user_id=user_id, ticker=payload.ticker,
            target_price=payload.target_price, direction=payload.direction,
        ))
    except PriceAlertLimitError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _to_schema(stored)


@price_alert_router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: PriceAlertUseCase = Depends(get_price_alert_use_case),
) -> None:
    if not await use_case.remove(user_id, alert_id):
        # 미존재와 남의 조건은 같은 404 — 존재 비노출(대화 히스토리 404 선례)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="조건을 찾지 못했습니다.")
