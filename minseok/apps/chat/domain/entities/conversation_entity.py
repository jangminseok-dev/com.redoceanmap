from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Message:
    """대화 한 턴 — ORM/프레임워크에 의존하지 않는 도메인 엔티티."""

    id: int
    conversation_id: int
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime
    payload: dict | None = None  # 답변에 곁들인 구조화 카드(추천 상권/종목) — 없으면 None


@dataclass(frozen=True, slots=True)
class Conversation:
    """대화 세션."""

    id: int
    created_at: datetime
    user_id: int | None = None  # 익명/구버전 대화는 None


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """대화 목록 한 줄 — 제목은 첫 사용자 메시지 요약.

    domain·label은 마지막 카드 payload의 요약이다(2026-08-17) — 목록이 "기록"이 아니라
    "작업 재개 지점"으로 읽히려면 어느 워크스페이스의 무엇이었는지가 행에 보여야 한다.
    카드 없는 대화(텍스트만·구버전)는 둘 다 None.
    """

    id: int
    title: str
    created_at: datetime
    domain: str | None = None  # "stock" | "market" — 마지막 카드 기준
    label: str | None = None  # 종목 심볼 또는 "첫 상권 이름 외 N곳"


def summarize_payload(payload: dict | None) -> tuple[str | None, str | None]:
    """마지막 카드 payload → (domain, label).

    payload 형태는 messages.payload(JSONB)에 저장된 그대로다 — stock 카드는
    {"stock": {"symbol": ...}}, 상권 추천은 {"recommendations": [{"name": ...}, ...]}.
    형태가 어긋나는 값(구버전·부분 저장)은 조용히 None으로 열화한다.
    """
    if not payload:
        return None, None
    stock = payload.get("stock")
    if isinstance(stock, dict) and stock.get("symbol"):
        return "stock", str(stock["symbol"])
    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        first = recommendations[0]
        name = first.get("name") if isinstance(first, dict) else None
        if name:
            extra = len(recommendations) - 1
            return "market", f"{name} 외 {extra}곳" if extra > 0 else str(name)
    return None, None
