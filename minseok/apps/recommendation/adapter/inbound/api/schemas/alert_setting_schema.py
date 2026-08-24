from __future__ import annotations

from pydantic import BaseModel


class AlertSettingSaveRequest(BaseModel):
    email_alerts: bool
    telegram_chat_id: str | None = None  # None·빈 문자열 = 텔레그램 채널 해제(I-7)


class AlertSettingResponse(BaseModel):
    email_alerts: bool
    telegram_chat_id: str | None = None


class AlertSettingMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
