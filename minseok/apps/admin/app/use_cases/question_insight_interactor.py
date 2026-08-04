from __future__ import annotations

from admin.app.dtos.question_insight_dto import (
    KindShareView,
    QuestionBoard,
    QuestionBoardQuery,
    QuestionRowView,
    RegionDemandView,
)
from admin.app.ports.input.question_insight_use_case import QuestionInsightUseCase
from hub.app.ports.output.question_insight_port import QuestionInsightPort


class QuestionInsightInteractor(QuestionInsightUseCase):
    """질문 인텔리전스 대장 — 집계는 chat 게이트웨이가 하고, 여기서는 비중 계산과
    화면 계약(정렬·상한)만 책임진다."""

    def __init__(self, questions: QuestionInsightPort) -> None:
        self._questions = questions

    async def get_board(self, query: QuestionBoardQuery) -> QuestionBoard:
        stats = await self._questions.stats(query.days)
        recent = await self._questions.recent_questions(query.limit)

        kind_total = sum(k.count for k in stats.kind_counts)
        return QuestionBoard(
            window_days=stats.window_days,
            total_questions=stats.total_questions,
            kinds=tuple(
                KindShareView(
                    kind=k.kind,
                    count=k.count,
                    # 분모는 질문 수가 아니라 답변 수 — 답 없이 끝난 대화가 있어도 100%가 유지된다
                    share_pct=round(k.count / kind_total * 100, 1) if kind_total else 0.0,
                )
                for k in stats.kind_counts
            ),
            nonseoul_regions=tuple(
                RegionDemandView(region=r.region, count=r.count)
                for r in stats.nonseoul_regions
            ),
            recent=tuple(
                QuestionRowView(
                    conversation_id=r.conversation_id,
                    question=r.question,
                    answer_kind=r.answer_kind,
                    asked_at=r.asked_at,
                )
                for r in recent
            ),
        )
