from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.question_insight_dto import QuestionInsightStats, QuestionRecord


class QuestionInsightPort(ABC):
    """질문 인텔리전스 추상 — admin(소비)과 chat(구현·영속: conversations/messages)을 잇는다.

    조회 전용이다(Record ↔ Directory 분리 선례 — 쓰기는 chat의 대화 저장 경로가 이미 한다).
    두 메서드를 한 포트에 두는 이유: 소비자가 하나(admin 질문 로그 화면)이고 둘 다
    "저장된 질문을 읽는다"는 같은 성질이다.
    """

    @abstractmethod
    async def recent_questions(self, limit: int = 50) -> tuple[QuestionRecord, ...]:
        """최근 질문(최신순). 답변 종류는 assistant payload·가드 문구에서 유도한다."""
        ...

    @abstractmethod
    async def stats(self, days: int = 30) -> QuestionInsightStats:
        """기간 내 질문 총량·답변 종류 분포·서울 외 지역 수요(가드 차단 건 기준)."""
        ...
