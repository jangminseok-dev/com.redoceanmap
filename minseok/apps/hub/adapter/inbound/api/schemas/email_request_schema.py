from __future__ import annotations

from pydantic import BaseModel, Field


class EmailRequestSchema(BaseModel):
    """수신자 필드는 없다 — 발송 대상은 서버가 로그인 계정 이메일로 정한다."""

    content: str = Field(min_length=1, max_length=2000)


class EmailRequestResultSchema(BaseModel):
    status: str
    detail: str
