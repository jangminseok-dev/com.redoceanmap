"""langchain_semantic_router.py — 랭체인 시멘틱 게이트웨이(hub/langchain-semantic, ROM 2.0).

ROM 1.0(`semantic_router.py`)과 분리한 이유: 계약이 다르다. 1.0은 단발 질의(prompt → answer)고
2.0은 세션 id를 주고받는 멀티턴 대화라, 한 라우터에 합치면 응답 스키마가 두 벌이 된다.
유스케이스 슬라이스당 라우터 1개 컨벤션에 따라 별도 슬라이스로 둔다 — 1.0은 그대로 살아 있다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.security import get_current_user_id
from hub.adapter.inbound.api.schemas.langchain_semantic_schema import (
    LangchainAskResponseSchema,
    LangchainAskSchema,
    LangchainSemanticResponseSchema,
)
from hub.app.dtos.langchain_semantic_dto import LangchainAskQuery, LangchainSemanticQuery
from hub.app.ports.input.langchain_semantic_use_case import LangchainSemanticUseCase
from hub.dependencies.langchain_semantic_provider import get_langchain_semantic_use_case

langchain_semantic_router = APIRouter(
    prefix="/langchain-semantic", tags=["langchain-semantic"]
)


@langchain_semantic_router.get("/myself", response_model=LangchainSemanticResponseSchema)
async def introduce_myself(
    gateway: LangchainSemanticUseCase = Depends(get_langchain_semantic_use_case),
) -> LangchainSemanticResponseSchema:
    result = await gateway.introduce_myself(
        LangchainSemanticQuery(id=11, name="랭체인 시멘틱 게이트웨이 (hub/langchain-semantic)")
    )
    return LangchainSemanticResponseSchema(
        id=result.id, name=result.name, introduction=result.introduction
    )


@langchain_semantic_router.post("/ask", response_model=LangchainAskResponseSchema)
async def ask(
    body: LangchainAskSchema,
    user_id: int = Depends(get_current_user_id),
    gateway: LangchainSemanticUseCase = Depends(get_langchain_semantic_use_case),
) -> LangchainAskResponseSchema:
    result = await gateway.ask(
        LangchainAskQuery(prompt=body.prompt, session_id=body.sessionId, user_id=user_id)
    )
    return LangchainAskResponseSchema(
        sessionId=result.session_id,
        destination=result.destination,
        entities=list(result.entities),
        answer=result.answer,
        chain=result.chain,
    )
