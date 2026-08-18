from datetime import datetime

from pydantic import BaseModel


class AskRequest(BaseModel):
    prompt: str
    conversationId: int | None = None


class ConversationSummarySchema(BaseModel):
    id: int
    title: str  # 첫 사용자 메시지 앞 40자
    createdAt: datetime
    # 마지막 카드 요약(2026-08-17) — 목록의 도메인 필터·재개 라벨용. 카드 없는 대화는 None
    domain: str | None = None  # "stock" | "market"
    label: str | None = None  # 종목 심볼 또는 "첫 상권 이름 외 N곳"


class ConversationMessageSchema(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    payload: dict | None = None  # 추천 상권/종목 카드 — 텍스트만인 메시지는 null
    createdAt: datetime
