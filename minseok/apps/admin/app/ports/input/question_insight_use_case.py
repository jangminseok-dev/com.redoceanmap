from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.question_insight_dto import QuestionBoard, QuestionBoardQuery


class QuestionInsightUseCase(ABC):
    """질문 인텔리전스 — 사용자가 무엇을 묻는지(수요 신호)를 운영자가 본다."""

    @abstractmethod
    async def get_board(self, query: QuestionBoardQuery) -> QuestionBoard:
        ...
