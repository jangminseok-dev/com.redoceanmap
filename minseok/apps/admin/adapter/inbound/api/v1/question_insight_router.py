from fastapi import APIRouter, Depends, Query

from admin.adapter.inbound.api.schemas.question_insight_schema import (
    KindShareSchema,
    QuestionBoardSchema,
    QuestionRowSchema,
    RegionDemandSchema,
)
from admin.app.dtos.question_insight_dto import QuestionBoardQuery
from admin.app.ports.input.question_insight_use_case import QuestionInsightUseCase
from admin.dependencies.question_insight_provider import get_question_insight_use_case
from core.security import require_permission

question_insight_router = APIRouter(prefix="/admin/questions", tags=["admin"])


@question_insight_router.get(
    "",
    response_model=QuestionBoardSchema,
    # 질문 분포는 분석 성격 — 신규 권한 시드 대신 analytics:read를 재사용한다
    dependencies=[Depends(require_permission("analytics:read"))],
)
async def get_question_board(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    use_case: QuestionInsightUseCase = Depends(get_question_insight_use_case),
) -> QuestionBoardSchema:
    """무엇을 묻는가 — 기간 내 질문 총량·답변 종류 분포·서울 외 수요·최근 질문.

    서울 외 지역 카운트는 결정론 가드가 실제로 차단한 질문 기준이다 —
    전국 확장의 우선순위를 정하는 실수요 신호.
    """
    board = await use_case.get_board(QuestionBoardQuery(days=days, limit=limit))
    return QuestionBoardSchema(
        window_days=board.window_days,
        total_questions=board.total_questions,
        kinds=[
            KindShareSchema(kind=k.kind, count=k.count, share_pct=k.share_pct)
            for k in board.kinds
        ],
        nonseoul_regions=[
            RegionDemandSchema(region=r.region, count=r.count)
            for r in board.nonseoul_regions
        ],
        recent=[
            QuestionRowSchema(
                conversation_id=r.conversation_id,
                question=r.question,
                answer_kind=r.answer_kind,
                asked_at=r.asked_at,
            )
            for r in board.recent
        ],
    )
