from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class QuestionRowSchema(BaseModel):
    conversation_id: int
    question: str
    answer_kind: str
    asked_at: datetime


class KindShareSchema(BaseModel):
    kind: str
    count: int
    share_pct: float


class RegionDemandSchema(BaseModel):
    region: str
    count: int


class QuestionBoardSchema(BaseModel):
    window_days: int
    total_questions: int
    kinds: list[KindShareSchema]
    nonseoul_regions: list[RegionDemandSchema]
    recent: list[QuestionRowSchema]
