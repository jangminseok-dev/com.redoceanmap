from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.futures_schema import (
    FuturesMarketResponse,
    FuturesMyselfResponse,
    FuturesPositionSchema,
    FuturesReceiptSchema,
    IndexPointSchema,
    OpenFuturesRequest,
)
from game.app.dtos.futures_dto import (
    CloseFuturesCommand,
    FuturesQuery,
    OpenFuturesCommand,
)
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
)
from game.app.ports.input.futures_use_case import FuturesUseCase
from game.app.use_cases.futures_interactor import MAX_TICKS, MIN_TICKS
from game.dependencies.futures_provider import get_futures_use_case
from game.domain.market import futures_contract as fut

futures_router = APIRouter(prefix="/game", tags=["game"])


@futures_router.get("/futures/myself", response_model=FuturesMyselfResponse)
async def describe_myself() -> FuturesMyselfResponse:
    """선물 슬라이스 자기소개 — 실제 기능과 제약을 밝힌다."""
    return FuturesMyselfResponse(
        id="game.futures",
        name="지수 선물",
        introduction=(
            "가상 지수 GXI의 근월물 하나를 사고팝니다. 현금정산이며 실물 인수도가 없습니다. "
            "지수는 게임 종목 12개의 상대가격 기하평균이고, 선물가는 만기가 가까울수록 "
            "현물에 수렴합니다. 실제 시장의 지수·선물과 무관합니다."
        ),
        endpoints=[
            "GET /game/futures — 지수·근월물·내 포지션(만기 도달분은 여기서 정산된다)",
            "POST /game/futures — 진입",
            "POST /game/futures/{position_id}/close — 중도 청산",
            "GET /game/futures/myself — 이 소개",
        ],
        constraints=[
            f"1계약 = 지수 1pt당 {fut.CONTRACT_MULTIPLIER_KRW}원 · "
            f"증거금 {int(fut.FUTURES_MARGIN_RATIO * 100)}%({fut.FUTURES_LEVERAGE}배)",
            f"만기는 {fut.FUTURES_EXPIRY_TICKS}틱(게임 3일)마다이며 거래 가능한 것은 근월물 하나입니다",
            f"만기까지 {fut.MIN_TICKS_TO_EXPIRY}틱 미만이면 새로 진입할 수 없습니다",
            "중도 강제청산은 없습니다 — 손실은 증거금까지로 막힙니다",
            "만기가 지나면 그 시점 현물 지수로 자동 정산됩니다(조회 시 확정)",
            "매매 지시를 하지 않습니다. 가격은 서버가 생성한 가상값입니다",
        ],
    )


@futures_router.get("/futures", response_model=FuturesMarketResponse)
async def get_market(
    ticks: int = Query(120, ge=MIN_TICKS, le=MAX_TICKS, description="지수 곡선 길이"),
    user_id: int = Depends(get_current_user_id),
    use_case: FuturesUseCase = Depends(get_futures_use_case),
) -> FuturesMarketResponse:
    try:
        result = await use_case.get_market(FuturesQuery(user_id=user_id, ticks=ticks))
    except InvalidOrder as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

    return FuturesMarketResponse(
        virtual=result.virtual,
        contractCode=result.contract_code,
        expiryTick=result.expiry_tick,
        ticksToExpiry=result.ticks_to_expiry,
        indexPoint=result.index_point,
        futuresPoint=result.futures_point,
        basisPct=result.basis_pct,
        contractValueKrw=result.contract_value_krw,
        marginPerContractKrw=result.margin_per_contract_krw,
        multiplierKrw=result.multiplier_krw,
        marginRatio=result.margin_ratio,
        maxContracts=result.max_contracts,
        series=[IndexPointSchema(tick=p.tick, point=p.point) for p in result.series],
        positions=[_position(p) for p in result.positions],
        investableKrw=result.investable_krw,
        tick=result.tick,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        seasonOver=result.season_over,
    )


@futures_router.post("/futures", response_model=FuturesReceiptSchema)
async def open_futures(
    body: OpenFuturesRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: FuturesUseCase = Depends(get_futures_use_case),
) -> FuturesReceiptSchema:
    try:
        receipt = await use_case.open(
            OpenFuturesCommand(user_id=user_id, side=body.side, contracts=body.contracts)
        )
    except (InvalidOrder, InsufficientCash, SeasonClosed) as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return _receipt(receipt)


@futures_router.post("/futures/{position_id}/close", response_model=FuturesReceiptSchema)
async def close_futures(
    position_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: FuturesUseCase = Depends(get_futures_use_case),
) -> FuturesReceiptSchema:
    try:
        receipt = await use_case.close(
            CloseFuturesCommand(user_id=user_id, position_id=position_id)
        )
    except PositionNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    return _receipt(receipt)


def _position(p) -> FuturesPositionSchema:
    return FuturesPositionSchema(
        id=p.id,
        contractCode=p.contract_code,
        side=p.side,
        contracts=p.contracts,
        entryPriceKrw=p.entry_price_krw,
        currentPriceKrw=p.current_price_krw,
        marketValueKrw=p.market_value_krw,
        unrealizedPnlKrw=p.unrealized_pnl_krw,
        unrealizedPct=p.unrealized_pct,
        expiresTick=p.expires_tick,
        ticksToExpiry=p.ticks_to_expiry,
    )


def _receipt(r) -> FuturesReceiptSchema:
    return FuturesReceiptSchema(
        positionId=r.position_id,
        contractCode=r.contract_code,
        side=r.side,
        contracts=r.contracts,
        priceKrw=r.price_krw,
        futuresPoint=r.futures_point,
        feeKrw=r.fee_krw,
        marginKrw=r.margin_krw,
        cashDeltaKrw=r.cash_delta_krw,
        realizedPnlKrw=r.realized_pnl_krw,
        cashKrw=r.cash_krw,
        expiresTick=r.expires_tick,
        tick=r.tick,
    )
