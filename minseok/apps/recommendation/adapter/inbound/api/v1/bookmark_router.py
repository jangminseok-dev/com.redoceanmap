"""bookmark_router.py — 관심 종목·상권 북마크(등록·내 목록·삭제)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from recommendation.adapter.inbound.api.schemas.bookmark_schema import (
    BookmarkCreateRequest,
    BookmarkDeleteResponse,
    BookmarkListResponse,
    BookmarkMyselfResponse,
    BookmarkResponse,
)
from recommendation.app.dtos.bookmark_dto import BookmarkDraft
from recommendation.app.ports.input.bookmark_use_case import BookmarkUseCase
from recommendation.app.use_cases.bookmark_interactor import BookmarkLimitError
from recommendation.dependencies.bookmark_provider import get_bookmark_use_case
from recommendation.domain.entities.bookmark_entity import Bookmark

bookmark_router = APIRouter(prefix="/bookmarks", tags=["recommendations"])


def _to_schema(b: Bookmark) -> BookmarkResponse:
    return BookmarkResponse(
        id=b.id, target_type=b.target_type, target_key=b.target_key,
        label=b.label, created_at=b.created_at,
    )


@bookmark_router.get("/myself", response_model=BookmarkMyselfResponse)
async def introduce_myself() -> BookmarkMyselfResponse:
    return BookmarkMyselfResponse(
        name="북마크",
        description=(
            "관심 종목·상권을 저장하고 다시 찾아가는 창구입니다. 같은 대상 재등록은 "
            "오류가 아니라 기존 항목을 돌려주고(멱등), 사용자당 200개까지 저장합니다. "
            "추천이나 매매 지시는 하지 않습니다 — 저장·조회·삭제가 전부입니다."
        ),
        endpoints=[
            "GET /bookmarks/myself — 이 소개",
            "POST /bookmarks — 등록 {target_type: stock|area, target_key, label}",
            "GET /bookmarks — 내 목록(최신순)",
            "DELETE /bookmarks/{target_type}/{target_key} — 삭제",
        ],
    )


@bookmark_router.post("", response_model=BookmarkResponse)
async def add_bookmark(
    payload: BookmarkCreateRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: BookmarkUseCase = Depends(get_bookmark_use_case),
) -> BookmarkResponse:
    try:
        saved = await use_case.add(BookmarkDraft(
            user_id=user_id, target_type=payload.target_type,
            target_key=payload.target_key, label=payload.label,
        ))
    except BookmarkLimitError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_schema(saved)


@bookmark_router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    user_id: int = Depends(get_current_user_id),
    use_case: BookmarkUseCase = Depends(get_bookmark_use_case),
) -> BookmarkListResponse:
    items = await use_case.list_mine(user_id)
    return BookmarkListResponse(items=[_to_schema(b) for b in items])


@bookmark_router.delete("/{target_type}/{target_key}", response_model=BookmarkDeleteResponse)
async def delete_bookmark(
    target_type: str,
    target_key: str,
    user_id: int = Depends(get_current_user_id),
    use_case: BookmarkUseCase = Depends(get_bookmark_use_case),
) -> BookmarkDeleteResponse:
    # 없는 것을 지워도 200(deleted=false) — 토글 UI의 중복 클릭이 오류가 아니게
    return BookmarkDeleteResponse(
        deleted=await use_case.remove(user_id, target_type, target_key)
    )
