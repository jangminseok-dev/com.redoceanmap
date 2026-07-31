from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.store_open_schema import (
    OpenStoreReceiptSchema,
    OpenStoreRequestSchema,
)
from game.app.dtos.store_open_dto import OpenStoreCommand
from game.app.exceptions import (
    AreaProfileUnavailable,
    InsufficientCash,
    InvalidOrder,
    SeasonClosed,
)
from game.app.ports.input.store_open_use_case import StoreOpenUseCase
from game.dependencies.store_open_provider import get_store_open_use_case

store_open_router = APIRouter(prefix="/game", tags=["game"])


@store_open_router.post("/stores", response_model=OpenStoreReceiptSchema)
async def open_store(
    body: OpenStoreRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: StoreOpenUseCase = Depends(get_store_open_use_case),
) -> OpenStoreReceiptSchema:
    try:
        receipt = await use_case.open_store(
            OpenStoreCommand(
                user_id=user_id,
                trdar_code=body.trdarCode,
                service_code=body.serviceCode,
                budget_krw=body.budgetKrw,
                facility_score=body.facilityScore,
                staff_count=body.staffCount,
                price_factor=body.priceFactor,
            )
        )
    except AreaProfileUnavailable as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except (InvalidOrder, InsufficientCash, SeasonClosed) as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

    return OpenStoreReceiptSchema(
        storeId=receipt.store_id,
        trdarName=receipt.trdar_name,
        serviceName=receipt.service_name,
        openedGameDay=receipt.opened_game_day,
        storeScale=receipt.store_scale,
        fitness=receipt.fitness,
        depositKrw=receipt.deposit_krw,
        interiorKrw=receipt.interior_krw,
        cashDeltaKrw=receipt.cash_delta_krw,
        cashKrw=receipt.cash_krw,
        assumedMonthlyRentKrw=receipt.assumed_monthly_rent_krw,
    )
