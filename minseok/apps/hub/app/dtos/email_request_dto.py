"""이메일 요청 계약 DTO. 허브가 소유하고 스포크(구현·소비)가 공유한다. 순수 객체."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailRequestCommand:
    """수신자를 담지 않는다 — 발송 대상은 요청자 본인이며 유스케이스가 id로 조회한다."""

    requester_id: int
    content: str


@dataclass(frozen=True)
class EmailRequestResult:
    status: str
    detail: str
