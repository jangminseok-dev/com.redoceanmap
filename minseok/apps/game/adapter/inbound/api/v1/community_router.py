from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.community_schema import (
    CommentSchema,
    CommunityMyselfSchema,
    PostReceiptSchema,
    PostSchema,
    ReportRequestSchema,
    ThreadResponseSchema,
    WriteCommentRequestSchema,
    WritePostRequestSchema,
)
from game.app.dtos.community_dto import (
    DeleteCommand,
    ReportCommand,
    ThreadQuery,
    ThreadView,
    WriteCommentCommand,
    WritePostCommand,
)
from game.app.exceptions import InvalidPost, PostNotFound, UnknownSymbol
from game.app.ports.input.community_use_case import CommunityUseCase
from game.app.use_cases.community_interactor import MAX_BODY_LENGTH, MAX_POSTS
from game.dependencies.community_provider import get_community_use_case

community_router = APIRouter(prefix="/game/community", tags=["game"])


def _to_schema(view: ThreadView) -> ThreadResponseSchema:
    return ThreadResponseSchema(
        symbol=view.symbol,
        name=view.name,
        posts=[
            PostSchema(
                id=p.id,
                author=p.author,
                body=p.body,
                createdTick=p.created_tick,
                createdAt=p.created_at,
                mine=p.mine,
                holdsSymbol=p.holds_symbol,
                comments=[
                    CommentSchema(
                        id=c.id,
                        author=c.author,
                        body=c.body,
                        createdTick=c.created_tick,
                        createdAt=c.created_at,
                        mine=c.mine,
                        holdsSymbol=c.holds_symbol,
                    )
                    for c in p.comments
                ],
            )
            for p in view.posts
        ],
    )


@community_router.get("/myself", response_model=CommunityMyselfSchema)
async def introduce_myself() -> CommunityMyselfSchema:
    return CommunityMyselfSchema(
        name="게임 종목 토론방 (game community)",
        introduction=(
            "모의투자 종목마다 붙는 토론방입니다. 사용자가 글과 댓글을 쓰고, 본인 글은 "
            "직접 지울 수 있으며, 문제되는 글은 신고할 수 있습니다. "
            "작성자 이름은 회원 실명이 아니라 회원 번호에서 만든 고정 가명입니다."
        ),
        endpoints=[
            "GET /game/community/posts?symbol= — 종목 토론방 글·댓글",
            "POST /game/community/posts — 글 작성",
            "DELETE /game/community/posts/{id} — 본인 글 삭제",
            "POST /game/community/posts/{id}/comments — 댓글 작성",
            "DELETE /game/community/comments/{id} — 본인 댓글 삭제",
            "POST /game/community/reports — 신고 접수",
        ],
        constraints=[
            "글쓴이가 만든 내용이며 서버나 AI가 생성한 글이 아닙니다.",
            "여기 적힌 의견은 투자 조언이 아니고, 게임 주가는 실제 시세가 아닙니다.",
            "신고는 접수만 합니다 — 신고했다고 글이 바로 내려가지 않습니다.",
            f"글·댓글은 {MAX_BODY_LENGTH}자까지, 한 번에 최근 {MAX_POSTS}개까지 읽습니다.",
            "대댓글·공감은 없습니다.",
        ],
    )


@community_router.get("/posts", response_model=ThreadResponseSchema)
async def read_thread(
    symbol: str = Query(description="게임 종목 코드"),
    limit: int = Query(20, ge=1, le=MAX_POSTS),
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> ThreadResponseSchema:
    try:
        view = await use_case.thread(
            ThreadQuery(symbol=symbol, viewer_user_id=user_id, limit=limit)
        )
    except UnknownSymbol as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    return _to_schema(view)


@community_router.post("/posts", response_model=PostReceiptSchema)
async def write_post(
    body: WritePostRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> PostReceiptSchema:
    try:
        receipt = await use_case.write_post(
            WritePostCommand(user_id=user_id, symbol=body.symbol, body=body.body)
        )
    except UnknownSymbol as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except InvalidPost as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return PostReceiptSchema(id=receipt.id, createdTick=receipt.created_tick)


@community_router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> None:
    try:
        await use_case.delete_post(DeleteCommand(user_id=user_id, target_id=post_id))
    except PostNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@community_router.post("/posts/{post_id}/comments", response_model=PostReceiptSchema)
async def write_comment(
    post_id: int,
    body: WriteCommentRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> PostReceiptSchema:
    try:
        receipt = await use_case.write_comment(
            WriteCommentCommand(user_id=user_id, post_id=post_id, body=body.body)
        )
    except PostNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except InvalidPost as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return PostReceiptSchema(id=receipt.id, createdTick=receipt.created_tick)


@community_router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> None:
    try:
        await use_case.delete_comment(DeleteCommand(user_id=user_id, target_id=comment_id))
    except PostNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@community_router.post("/reports", status_code=204)
async def report(
    body: ReportRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: CommunityUseCase = Depends(get_community_use_case),
) -> None:
    try:
        await use_case.report(
            ReportCommand(
                reporter_user_id=user_id,
                target_type=body.targetType,
                target_id=body.targetId,
                reason=body.reason,
            )
        )
    except InvalidPost as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
