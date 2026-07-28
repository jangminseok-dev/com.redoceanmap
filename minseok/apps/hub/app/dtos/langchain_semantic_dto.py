"""langchain_semantic_dto.py — 랭체인 시멘틱 게이트웨이(ROM 2.0) 레이어 간 전달 객체."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LangchainSemanticQuery:

    id: int
    name: str


@dataclass(frozen=True)
class LangchainSemanticResponse:

    id: int
    name: str
    introduction: str


@dataclass(frozen=True)
class LangchainAskQuery:
    """세션이 없으면(session_id=None) 인터랙터가 새로 연다."""

    prompt: str
    session_id: int | None = None
    user_id: int | None = None


@dataclass(frozen=True)
class LangchainAskResponse:

    session_id: int
    destination: str
    entities: tuple[str, ...]
    answer: str
    chain: str  # 실제로 태운 LCEL 체인 이름 — 어느 경로로 답이 나왔는지 관찰용


@dataclass(frozen=True)
class EngineTurn:
    """랭체인 엔진에 넘기는 한 턴의 입력. history는 (role, content) 오래된 순."""

    prompt: str
    destination: str
    history: tuple[tuple[str, str], ...] = ()
    context: str | None = None  # 있으면 근거 체인, 없으면 일반 대화 체인


@dataclass(frozen=True)
class EngineAnswer:

    answer: str
    chain: str
