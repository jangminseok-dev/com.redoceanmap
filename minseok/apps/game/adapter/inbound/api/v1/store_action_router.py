from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.store_action_schema import (
    CloseStoreResponse,
    StoreActionMyselfResponse,
    StoreDecisionRequest,
    StoreDecisionResponse,
)
from game.app.dtos.store_action_dto import CloseStoreCommand, StoreDecisionCommand
from game.app.exceptions import InsufficientCash, InvalidOrder, SeasonClosed, StoreNotFound
from game.app.ports.input.store_action_use_case import StoreActionUseCase
from game.app.use_cases.store_action_interactor import (
    MAX_FACILITY_SCORE,
    MAX_PRICE_FACTOR,
    MAX_STAFF,
    MIN_PRICE_FACTOR,
)
from game.dependencies.store_action_provider import get_store_action_use_case
from game.domain.economy.rule_coefficients import MAX_CONCURRENT_STORES

store_action_router = APIRouter(prefix="/game", tags=["game"])


@store_action_router.get("/stores/actions/myself", response_model=StoreActionMyselfResponse)
async def describe_myself() -> StoreActionMyselfResponse:
    """운영 액션 슬라이스 자기소개 — 실제 기능과 제약을 밝힌다."""
    return StoreActionMyselfResponse(
        id="game.store_action",
        name="가게 운영",
        introduction=(
            "창업한 가게의 가격·직원·시설을 조정하고 폐업합니다. "
            "변경은 다음 게임일부터 적용되며, 이미 지나간 날의 매출은 그때의 결정으로 "
            "다시 계산됩니다 — 과거는 바뀌지 않습니다."
        ),
        endpoints=[
            "POST /game/stores/{store_id}/decisions — 가격·직원·시설 조정",
            "POST /game/stores/{store_id}/close — 폐업(보증금 회수)",
            "GET /game/stores/actions/myself — 이 소개",
        ],
        constraints=[
            f"가격 계수 {MIN_PRICE_FACTOR}~{MAX_PRICE_FACTOR} · 직원 0~{MAX_STAFF}명 "
            f"· 시설 최대 {MAX_FACILITY_SCORE}점",
            "시설은 줄일 수 없습니다 — 인테리어비는 회수되지 않습니다",
            "운영 변경은 게임 1일에 한 번입니다",
            "폐업하면 보증금은 전액 돌려받고 인테리어는 회수되지 않습니다",
            f"가게는 동시에 {MAX_CONCURRENT_STORES}곳까지, "
            "n+1호점은 흑자 분기 결산 n회가 필요합니다",
            "매출·손익은 게임 규칙으로 만든 가정치이며 실제 창업 결과가 아닙니다",
        ],
    )


@store_action_router.post("/stores/{store_id}/decisions", response_model=StoreDecisionResponse)
async def decide(
    store_id: int,
    body: StoreDecisionRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: StoreActionUseCase = Depends(get_store_action_use_case),
) -> StoreDecisionResponse:
    try:
        receipt = await use_case.decide(
            StoreDecisionCommand(
                user_id=user_id,
                store_id=store_id,
                price_factor=body.priceFactor,
                staff_count=body.staffCount,
                facility_score=body.facilityScore,
            )
        )
    except StoreNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except (InvalidOrder, InsufficientCash, SeasonClosed) as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

    return StoreDecisionResponse(
        storeId=receipt.store_id,
        effectiveFromDay=receipt.effective_from_day,
        priceFactor=receipt.price_factor,
        staffCount=receipt.staff_count,
        facilityScore=receipt.facility_score,
        facilityAdded=receipt.facility_added,
        interiorCostKrw=receipt.interior_cost_krw,
        cashDeltaKrw=receipt.cash_delta_krw,
        cashKrw=receipt.cash_krw,
    )


@store_action_router.post("/stores/{store_id}/close", response_model=CloseStoreResponse)
async def close_store(
    store_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: StoreActionUseCase = Depends(get_store_action_use_case),
) -> CloseStoreResponse:
    try:
        receipt = await use_case.close(CloseStoreCommand(user_id=user_id, store_id=store_id))
    except StoreNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except InvalidOrder as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

    return CloseStoreResponse(
        storeId=receipt.store_id,
        closedGameDay=receipt.closed_game_day,
        depositRefundKrw=receipt.deposit_refund_krw,
        interiorLostKrw=receipt.interior_lost_krw,
        cashDeltaKrw=receipt.cash_delta_krw,
        cashKrw=receipt.cash_krw,
        pendingSettlement=receipt.pending_settlement,
    )
