from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.store_daily_schema import (
    CustomerBucketSchema,
    DailyRowSchema,
    StoreDailyResponseSchema,
    StoreSummarySchema,
)
from game.app.dtos.store_daily_dto import StoreDailyQuery
from game.app.exceptions import StoreNotFound
from game.app.ports.input.store_daily_use_case import StoreDailyUseCase
from game.app.use_cases.store_daily_interactor import MAX_DAYS
from game.dependencies.store_daily_provider import get_store_daily_use_case

store_daily_router = APIRouter(prefix="/game", tags=["game"])


@store_daily_router.get("/stores", response_model=list[StoreSummarySchema])
async def list_stores(
    user_id: int = Depends(get_current_user_id),
    use_case: StoreDailyUseCase = Depends(get_store_daily_use_case),
) -> list[StoreSummarySchema]:
    stores = await use_case.list_stores(user_id)
    return [
        StoreSummarySchema(
            storeId=s.store_id,
            trdarName=s.trdar_name,
            serviceName=s.service_name,
            status=s.status,
            openedGameDay=s.opened_game_day,
            daysOpen=s.days_open,
            storeScale=s.store_scale,
            fitness=s.fitness,
            cumulativeSalesKrw=s.cumulative_sales_krw,
            cumulativeProfitKrw=s.cumulative_profit_krw,
        )
        for s in stores
    ]


@store_daily_router.get("/stores/{store_id}", response_model=StoreDailyResponseSchema)
async def get_store_daily(
    store_id: int,
    days: int = Query(14, ge=1, le=MAX_DAYS, description="최근 며칠을 보여줄지"),
    user_id: int = Depends(get_current_user_id),
    use_case: StoreDailyUseCase = Depends(get_store_daily_use_case),
) -> StoreDailyResponseSchema:
    try:
        result = await use_case.get_daily(
            StoreDailyQuery(user_id=user_id, store_id=store_id, days=days)
        )
    except StoreNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e

    buckets = lambda items: [  # noqa: E731
        CustomerBucketSchema(label=b.label, count=b.count) for b in items
    ]
    return StoreDailyResponseSchema(
        storeId=result.store_id,
        trdarName=result.trdar_name,
        serviceName=result.service_name,
        status=result.status,
        openedGameDay=result.opened_game_day,
        daysOpen=result.days_open,
        storeScale=result.store_scale,
        fitness=result.fitness,
        seats=result.seats,
        depositKrw=result.deposit_krw,
        interiorKrw=result.interior_krw,
        observedSalesPerStore=result.observed_sales_per_store,
        observedTicketPrice=result.observed_ticket_price,
        assumedMonthlyRentKrw=result.assumed_monthly_rent_krw,
        cumulativeSalesKrw=result.cumulative_sales_krw,
        cumulativeProfitKrw=result.cumulative_profit_krw,
        averageTurnedAwayRatio=result.average_turned_away_ratio,
        rows=[
            DailyRowSchema(
                gameDay=r.game_day,
                simulatedSalesKrw=r.simulated_sales_krw,
                simulatedCustomerCount=r.simulated_customer_count,
                capacityCustomerCount=r.capacity_customer_count,
                turnedAwayRatio=r.turned_away_ratio,
                assumedRentKrw=r.assumed_rent_krw,
                assumedLaborKrw=r.assumed_labor_krw,
                assumedCogsKrw=r.assumed_cogs_krw,
                assumedUtilityKrw=r.assumed_utility_krw,
                profitKrw=r.profit_krw,
            )
            for r in result.rows
        ],
        customersByAge=buckets(result.customers_by_age),
        customersByHour=buckets(result.customers_by_hour),
        customersByTaste=buckets(result.customers_by_taste),
        tick=result.tick,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        seasonOver=result.season_over,
    )
