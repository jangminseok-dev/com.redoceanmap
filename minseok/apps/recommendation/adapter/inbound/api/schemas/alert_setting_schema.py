from __future__ import annotations

from pydantic import BaseModel


class AlertSettingSaveRequest(BaseModel):
    email_alerts: bool


class AlertSettingResponse(BaseModel):
    email_alerts: bool


class AlertSettingMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
