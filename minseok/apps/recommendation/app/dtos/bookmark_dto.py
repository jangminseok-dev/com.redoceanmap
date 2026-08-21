from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookmarkDraft:
    """북마크 등록 입력 — 정규화(공백·대문자)는 인터랙터가 한다."""

    user_id: int
    target_type: str
    target_key: str
    label: str
