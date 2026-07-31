from fastapi import APIRouter, Depends

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.settlement_schema import (
    AdviceSchema,
    SettlementListResponseSchema,
    SettlementSchema,
)
from game.app.dtos.settlement_dto import SettlementQuery
from game.app.ports.input.settlement_use_case import SettlementUseCase
from game.dependencies.settlement_provider import get_settlement_use_case

settlement_router = APIRouter(prefix="/game", tags=["game"])


@settlement_router.get("/settlements", response_model=SettlementListResponseSchema)
async def list_settlements(
    user_id: int = Depends(get_current_user_id),
    use_case: SettlementUseCase = Depends(get_settlement_use_case),
) -> SettlementListResponseSchema:
    """분기 결산 목록.

    **조회가 곧 정산 시점이다.** cron이 없으므로 밀린 분기를 여기서 확정한다(지연 실행).
    멱등하므로 여러 번 불러도 같은 결과다.
    """
    result = await use_case.run_and_list(SettlementQuery(user_id=user_id))
    return SettlementListResponseSchema(
        settlements=[
            SettlementSchema(
                storeId=s.store_id,
                trdarName=s.trdar_name,
                serviceName=s.service_name,
                gameQuarter=s.game_quarter,
                daysCounted=s.days_counted,
                simulatedSalesKrw=s.simulated_sales_krw,
                assumedRentKrw=s.assumed_rent_krw,
                assumedLaborKrw=s.assumed_labor_krw,
                assumedCogsKrw=s.assumed_cogs_krw,
                assumedUtilityKrw=s.assumed_utility_krw,
                profitKrw=s.profit_krw,
                customerCount=s.customer_count,
                averageTurnedAwayRatio=s.average_turned_away_ratio,
                performanceRatio=s.performance_ratio,
                advices=[AdviceSchema(tone=a.tone, message=a.message) for a in s.advices],
            )
            for s in result.settlements
        ],
        newlySettled=result.newly_settled,
        totalProfitKrw=result.total_profit_krw,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        seasonOver=result.season_over,
    )
