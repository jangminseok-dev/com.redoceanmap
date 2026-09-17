from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from stock.adapter.inbound.api.schemas.stock_board_schema import StockBoardResponse
from stock.app.dtos.stock_board_dto import BoardQuery
from stock.app.ports.input.stock_board_use_case import StockBoardUseCase
from stock.dependencies.stock_board_provider import get_stock_board_use_case

stock_board_router = APIRouter(prefix="/stock", tags=["stock"])


@stock_board_router.get("/board", response_model=StockBoardResponse)
async def get_stock_board(
    horizon: int = Query(default=5, ge=1, le=20),
    limit: int = Query(default=40, ge=1, le=200),
    # 기본은 위험 신호 순(2026-09-17 재설계) — 방향 신호는 겹침 보정 재검증 미달이라 정렬 기준에서 내렸다
    order: str = Query(default="risk", pattern="^(risk|signal)$"),
    use_case: StockBoardUseCase = Depends(get_stock_board_use_case),
) -> StockBoardResponse:
    # 스냅샷이 없으면 rows가 빈 배열 — 404가 아니다(수집 전에도 화면이 떠야 한다)
    view = await use_case.board(BoardQuery(horizon=horizon, limit=limit, order=order))
    return StockBoardResponse(**asdict(view))
