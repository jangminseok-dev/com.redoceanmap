"""질문 인텔리전스 계약 DTO — admin(소비)과 chat(구현)을 잇는다.

사용자가 무엇을 묻는지가 수요 검증의 1차 신호다. chat이 이미 영속하는
conversations/messages에서 집계만 내리며, 개인 식별 정보(user_id·이메일)는
계약에 싣지 않는다 — 운영 화면이 필요로 하는 것은 신원이 아니라 질문 분포다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QuestionRecord:
    """질문 1건 — 답변 종류는 assistant payload에서 유도한 관측값이다."""

    conversation_id: int
    question: str
    answer_kind: str  # market | stock | market_news | nonseoul | text
    asked_at: datetime


@dataclass(frozen=True)
class KindCount:
    kind: str
    count: int


@dataclass(frozen=True)
class RegionDemand:
    """서울 외 지역 질문 수 — 결정론 가드가 차단한 실수요. 전국 확장 우선순위 근거."""

    region: str
    count: int


@dataclass(frozen=True)
class QuestionInsightStats:
    window_days: int
    total_questions: int
    kind_counts: tuple[KindCount, ...]
    nonseoul_regions: tuple[RegionDemand, ...]
