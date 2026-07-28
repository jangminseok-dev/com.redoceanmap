"""session_entity.py — 랭체인 챗봇 세션의 순수 도메인 엔티티(ORM·프레임워크 무의존)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LangchainSession:
    """랭체인 대화 세션 — 멀티턴 메모리의 소유 단위."""

    id: int
    created_at: datetime
    user_id: int | None = None


@dataclass(frozen=True, slots=True)
class LangchainTurn:
    """세션 안의 한 턴. destination은 그 턴을 만든 시멘틱 분류 결과(assistant 턴에만 의미)."""

    id: int
    session_id: int
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime
    destination: str | None = None
