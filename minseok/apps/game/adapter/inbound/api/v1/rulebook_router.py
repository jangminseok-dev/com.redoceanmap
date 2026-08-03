from fastapi import APIRouter, Depends

from game.adapter.inbound.api.schemas.rulebook_schema import RulebookResponseSchema
from game.app.dtos.rulebook_dto import RulebookQuery
from game.app.ports.input.rulebook_use_case import RulebookUseCase
from game.dependencies.rulebook_provider import get_rulebook_use_case

rulebook_router = APIRouter(prefix="/game", tags=["game"])


@rulebook_router.get("/myself", response_model=RulebookResponseSchema)
async def introduce_myself(
    rulebook: RulebookUseCase = Depends(get_rulebook_use_case)
) -> RulebookResponseSchema:
    result = await rulebook.introduce_myself(
        RulebookQuery(
            id=12,
            name="게임 (game)"
        )
    )
    return RulebookResponseSchema(
        id=result.id,
        name=result.name,
        introduction=result.introduction,
        epochId=result.epoch_id,
        ruleVersion=result.rule_version,
        tick=result.tick,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        dayOfQuarter=result.day_of_quarter,
        seasonOver=result.season_over,
        ticksRemaining=result.ticks_remaining,
        initialCashKrw=result.initial_cash_krw,
        reservedCashKrw=result.reserved_cash_krw,
        feeRate=result.fee_rate,
        shortCarryRatePerGameDay=result.short_carry_rate_per_game_day,
        leverageTiers=list(result.leverage_tiers),
        maintenanceMarginRatio=result.maintenance_margin_ratio,
        leveragedExpiryTicks=result.leveraged_expiry_ticks,
        maxLeveragedPositions=result.max_leveraged_positions,
        ticksPerGameDay=result.ticks_per_game_day,
    )
