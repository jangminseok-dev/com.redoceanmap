from fastapi import APIRouter, Depends, HTTPException

from admin.adapter.inbound.api.schemas.game_ops_schema import (
    GameOpsBoardSchema,
    GameWalletResponseSchema,
    GrantCapitalRequestSchema,
    GrantCapitalResponseSchema,
    IntervenePriceRequestSchema,
    InterventionSchema,
    SymbolOptionSchema,
)
from admin.app.dtos.game_ops_dto import (
    GameWalletQuery,
    GrantCapitalCommand,
    InterveneCommand,
    InterventionView,
)
from admin.app.ports.input.game_ops_use_case import GameOpsUseCase
from admin.dependencies.game_ops_provider import get_game_ops_use_case
from core.security import require_permission

game_ops_router = APIRouter(prefix="/admin/game", tags=["admin"])


def _to_schema(v: InterventionView) -> InterventionSchema:
    return InterventionSchema(
        id=v.id,
        scope=v.scope,
        target=v.target,
        target_name=v.target_name,
        from_game_day=v.from_game_day,
        shock_pct=v.shock_pct,
        drift_pct_per_day=v.drift_pct_per_day,
        duration_days=v.duration_days,
        headline=v.headline,
        note=v.note,
        in_effect=v.in_effect,
    )


@game_ops_router.get(
    "/wallets/{user_id}",
    response_model=GameWalletResponseSchema,
    dependencies=[Depends(require_permission("game:read"))],
)
async def get_wallet(
    user_id: int,
    use_case: GameOpsUseCase = Depends(get_game_ops_use_case),
) -> GameWalletResponseSchema:
    """유저 지갑 요약. 회원 검색은 `/admin/members`가 하고 여기는 user_id만 받는다."""
    result = await use_case.get_wallet(GameWalletQuery(user_id=user_id))
    return GameWalletResponseSchema(
        user_id=result.user_id,
        email=result.email,
        exists=result.exists,
        cash_krw=result.cash_krw,
        epoch_id=result.epoch_id,
        rule_version=result.rule_version,
        open_position_count=result.open_position_count,
        ledger_total_krw=result.ledger_total_krw,
        ledger_matches=result.ledger_matches,
    )


@game_ops_router.post(
    "/wallets/{user_id}/grants",
    response_model=GrantCapitalResponseSchema,
    dependencies=[Depends(require_permission("game:write"))],
)
async def grant_capital(
    user_id: int,
    body: GrantCapitalRequestSchema,
    admin_id: int = Depends(require_permission("game:write")),
    use_case: GameOpsUseCase = Depends(get_game_ops_use_case),
) -> GrantCapitalResponseSchema:
    """자본 지급·회수. 원장에 `admin` 한 줄이 함께 들어간다."""
    try:
        result = await use_case.grant_capital(
            GrantCapitalCommand(
                user_id=user_id,
                amount_krw=body.amount_krw,
                reason=body.reason,
                granted_by=admin_id,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return GrantCapitalResponseSchema(
        user_id=result.user_id,
        amount_krw=result.amount_krw,
        cash_krw=result.cash_krw,
        game_day=result.game_day,
    )


@game_ops_router.get(
    "/market",
    response_model=GameOpsBoardSchema,
    dependencies=[Depends(require_permission("game:read"))],
)
async def get_board(
    use_case: GameOpsUseCase = Depends(get_game_ops_use_case),
) -> GameOpsBoardSchema:
    """개입 대상(전 종목 현재가·묶음 업종)과 개입 이력."""
    board = await use_case.get_board()
    return GameOpsBoardSchema(
        symbols=[
            SymbolOptionSchema(
                symbol=s.symbol,
                name=s.name,
                sector_group=s.sector_group,
                price_krw=s.price_krw,
                meme=s.meme,
            )
            for s in board.symbols
        ],
        sector_groups=list(board.sector_groups),
        interventions=[_to_schema(v) for v in board.interventions],
        max_shock_pct=board.max_shock_pct,
        max_drift_pct_per_day=board.max_drift_pct_per_day,
        max_duration_days=board.max_duration_days,
    )


@game_ops_router.post(
    "/interventions",
    response_model=InterventionSchema,
    dependencies=[Depends(require_permission("game:write"))],
)
async def intervene_price(
    body: IntervenePriceRequestSchema,
    admin_id: int = Depends(require_permission("game:write")),
    use_case: GameOpsUseCase = Depends(get_game_ops_use_case),
) -> InterventionSchema:
    """주가 개입 — **지금부터 앞으로만** 적용된다.

    과거 주가는 바뀌지 않는다(이미 체결된 체결가·결산이 소급 변조되지 않게). 잘못 넣었으면
    삭제가 아니라 **반대 방향 개입**으로 정정한다.
    """
    try:
        result = await use_case.intervene(
            InterveneCommand(
                scope=body.scope,
                target=body.target,
                shock_pct=body.shock_pct,
                drift_pct_per_day=body.drift_pct_per_day,
                duration_days=body.duration_days,
                headline=body.headline,
                note=body.note,
                created_by=admin_id,
                target_price_krw=body.target_price_krw,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _to_schema(result)
