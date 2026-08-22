from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileDraft:
    """프로파일 저장 입력 — 값 검증(어휘 밖 값 거부)은 도메인 엔티티가 한다."""

    user_id: int
    purpose: str
    risk_level: int
    budget_band: str
    debt_burden: str
    horizon: str
