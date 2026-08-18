import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from chat.adapter.inbound.api.schemas.chat_schema import (
    AskRequest,
    ConversationMessageSchema,
    ConversationSummarySchema,
)
from chat.app.dtos.chat_dto import AskResponse
from chat.app.exceptions import (
    ChatError,
    CommercialDataUnavailableError,
    ConversationNotFoundError,
    InvalidLLMResponseError,
    NoValidAreaError,
)
from chat.app.ports.input.chat_use_case import ChatUseCase
from chat.dependencies.chat_provider import get_chat_use_case
from core.security import get_current_user_id

chat_router = APIRouter(prefix="/chat", tags=["chat"])

# 앱 계층 예외 → HTTP 상태코드 변환은 인바운드 어댑터의 책임
_STATUS_BY_ERROR: dict[type[ChatError], int] = {
    CommercialDataUnavailableError: 503,
    NoValidAreaError: 422,
    InvalidLLMResponseError: 500,
    ConversationNotFoundError: 404,
}


@chat_router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ChatUseCase = Depends(get_chat_use_case),
):
    try:
        return await use_case.ask(body.prompt, body.conversationId, user_id=user_id)
    except ChatError as e:
        raise HTTPException(status_code=_STATUS_BY_ERROR[type(e)], detail=e.detail)


@chat_router.post("/ask/progress")
async def ask_progress(
    body: AskRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ChatUseCase = Depends(get_chat_use_case),
):
    """/ask와 같은 일을 하되 진행 단계를 SSE로 흘린다.

    phase 왕복(p95 실측 ~1.5분) 동안 화면이 침묵하지 않게 한다.
    이벤트: {"type":"stage","stage","label"}* → {"type":"result","data":AskResponse}
            | {"type":"error","status","message"}
    """
    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(use_case.ask(
            body.prompt, body.conversationId, user_id=user_id,
            on_stage=lambda stage, label: queue.put_nowait(
                {"type": "stage", "stage": stage, "label": label}
            ),
        ))
        while not (task.done() and queue.empty()):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.3)
            except asyncio.TimeoutError:
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        try:
            result = task.result()
            payload = {"type": "result", "data": result.model_dump()}
        except ChatError as e:
            payload = {"type": "error", "status": _STATUS_BY_ERROR[type(e)], "message": e.detail}
        except Exception:  # SSE는 이미 200 — 본문 이벤트로만 오류를 전할 수 있다
            payload = {"type": "error", "status": 500, "message": "일시적인 오류가 발생했어요."}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@chat_router.post("/stream")
async def stream(
    body: AskRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ChatUseCase = Depends(get_chat_use_case),
):
    """대화형 답변을 SSE(text/event-stream)로 토큰 스트리밍한다."""
    async def event_gen():
        async for event in use_case.stream_reply(body.prompt, body.conversationId, user_id=user_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@chat_router.get("/conversations", response_model=list[ConversationSummarySchema])
async def list_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> list[ConversationSummarySchema]:
    summaries = await use_case.list_conversations(user_id, limit)
    return [
        ConversationSummarySchema(
            id=s.id, title=s.title, createdAt=s.created_at, domain=s.domain, label=s.label,
        )
        for s in summaries
    ]


@chat_router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageSchema],
)
async def conversation_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: ChatUseCase = Depends(get_chat_use_case),
) -> list[ConversationMessageSchema]:
    try:
        messages = await use_case.conversation_messages(conversation_id, user_id)
    except ChatError as e:
        raise HTTPException(status_code=_STATUS_BY_ERROR[type(e)], detail=e.detail)
    return [
        ConversationMessageSchema(
            role=m.role, content=m.content, payload=m.payload, createdAt=m.created_at,
        )
        for m in messages
    ]
