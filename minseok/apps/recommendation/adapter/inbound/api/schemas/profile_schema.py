from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileSaveRequest(BaseModel):
    purpose: Literal["startup", "invest", "both"]
    risk_level: int = Field(ge=1, le=5)
    budget_band: Literal["under_30m", "30m_50m", "50m_100m", "100m_300m", "over_300m"]
    debt_burden: Literal["none", "manageable", "heavy"]
    horizon: Literal["short", "mid", "long"]


class ProfileResponse(BaseModel):
    purpose: str
    risk_level: int
    budget_band: str
    debt_burden: str
    horizon: str
    updated_at: datetime


class ProfileEnvelope(BaseModel):
    """내 프로파일 조회 — 미작성이면 profile=null(404가 아니라 정상 상태)."""

    profile: ProfileResponse | None


class ProfileDeleteResponse(BaseModel):
    deleted: bool


class ProfileMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
