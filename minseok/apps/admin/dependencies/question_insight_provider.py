from __future__ import annotations

from fastapi import Depends

from admin.app.ports.input.question_insight_use_case import QuestionInsightUseCase
from admin.app.use_cases.question_insight_interactor import QuestionInsightInteractor
from hub.app.ports.output.question_insight_port import QuestionInsightPort
from hub.dependencies.question_insight_provider import get_question_insight_port


def get_question_insight_use_case(
    questions: QuestionInsightPort = Depends(get_question_insight_port),
) -> QuestionInsightUseCase:
    return QuestionInsightInteractor(questions=questions)
