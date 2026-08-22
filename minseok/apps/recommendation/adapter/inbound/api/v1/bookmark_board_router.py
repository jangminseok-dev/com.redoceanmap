"""bookmark_board_router.py — 관심 보드(③-M7): 내 북마크의 '지금'(종목 신호·상권 점수)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import get_current_user_id
from recommendation.adapter.inbound.api.schemas.bookmark_board_schema import (
    BoardAreaStatus,
    BoardStockStatus,
    BookmarkBoardItemResponse,
    BookmarkBoardMyselfResponse,
    BookmarkBoardResponse,
)
from recommendation.app.dtos.bookmark_board_dto import BookmarkBoardItem
from recommendation.app.ports.input.bookmark_board_use_case import BookmarkBoardUseCase
from recommendation.dependencies.bookmark_board_provider import get_bookmark_board_use_case

bookmark_board_router = APIRouter(prefix="/bookmarks/board", tags=["recommendations"])


def _to_schema(item: BookmarkBoardItem) -> BookmarkBoardItemResponse:
    b = item.bookmark
    stock = None
    if item.stock is not None:
        s = item.stock
        stock = BoardStockStatus(
            ticker=s.ticker, as_of=s.as_of, direction=s.direction, price=s.price,
            change_pct=s.change_pct, ready=s.ready, price_as_of=s.price_as_of,
        )
    area = None
    if item.area is not None:
        # "전분기 대비"는 종합점수 컴포넌트 중 매출 성장(QoQ)을 뽑아 쓴다 — 산출 불가면 None
        growth = next((c for c in item.area.components if c.key == "sales_growth"), None)
        area = BoardAreaStatus(
            total=item.area.total, grade=item.area.grade,
            sales_qoq_pct=growth.value if growth else None,
            seoul_qoq_pct=growth.benchmark if growth else None,
        )
    return BookmarkBoardItemResponse(
        id=b.id, target_type=b.target_type, target_key=b.target_key,
        label=b.label, created_at=b.created_at, stock=stock, area=area,
    )


@bookmark_board_router.get("/myself", response_model=BookmarkBoardMyselfResponse)
async def introduce_myself() -> BookmarkBoardMyselfResponse:
    return BookmarkBoardMyselfResponse(
        name="관심 보드",
        description=(
            "내가 찜한 종목·상권의 '지금'을 한 번에 보여주는 창구입니다. 종목은 최신 신호"
            "(방향·전일 대비·검증 참고 여부, 일일 동결 스냅샷 기준 — 준실시간 아님), 상권은 "
            "서울 평균 대비 종합점수와 전분기 대비 매출 성장을 붙입니다. 상태를 만들 데이터가 "
            "없는 항목은 상태 없이 나갑니다(목록은 항상 뜹니다). 매매 지시나 순위 추천은 "
            "하지 않으며, 정렬은 등록 최신순 고정입니다."
        ),
        endpoints=[
            "GET /bookmarks/board/myself — 이 소개",
            "GET /bookmarks/board — 내 관심 보드(등록 최신순)",
        ],
    )


@bookmark_board_router.get("", response_model=BookmarkBoardResponse)
async def my_board(
    user_id: int = Depends(get_current_user_id),
    use_case: BookmarkBoardUseCase = Depends(get_bookmark_board_use_case),
) -> BookmarkBoardResponse:
    items = await use_case.board(user_id)
    return BookmarkBoardResponse(items=[_to_schema(i) for i in items])
