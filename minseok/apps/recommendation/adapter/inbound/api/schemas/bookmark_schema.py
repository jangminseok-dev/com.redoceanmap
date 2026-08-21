from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BookmarkCreateRequest(BaseModel):
    target_type: Literal["stock", "area"]
    target_key: str = Field(min_length=1, max_length=30)
    label: str = Field(default="", max_length=100)


class BookmarkResponse(BaseModel):
    id: int
    target_type: str
    target_key: str
    label: str
    created_at: datetime


class BookmarkListResponse(BaseModel):
    items: list[BookmarkResponse]


class BookmarkDeleteResponse(BaseModel):
    deleted: bool


class BookmarkMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
