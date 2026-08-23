from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertSettingDraft:
    """수신 설정 저장 입력 — 회원당 1행 upsert."""

    user_id: int
    email_alerts: bool
