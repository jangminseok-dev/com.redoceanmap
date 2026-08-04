from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QuestionBoardQuery:
    days: int
    limit: int


@dataclass(frozen=True)
class QuestionRowView:
    conversation_id: int
    question: str
    answer_kind: str
    asked_at: datetime


@dataclass(frozen=True)
class KindShareView:
    kind: str
    count: int
    share_pct: float  # 답변 총량 대비 비중 — 화면이 재계산하지 않게 여기서 확정


@dataclass(frozen=True)
class RegionDemandView:
    region: str
    count: int


@dataclass(frozen=True)
class QuestionBoard:
    window_days: int
    total_questions: int
    kinds: tuple[KindShareView, ...]
    nonseoul_regions: tuple[RegionDemandView, ...]
    recent: tuple[QuestionRowView, ...]
