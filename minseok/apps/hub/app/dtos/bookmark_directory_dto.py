"""북마크 열람 계약 DTO.

허브가 공개하는 앱 간 협력 계약. recommendation(스포크)이 채워서 반환하고
허브 bookmark_alert 유스케이스(③-M3 알림)가 소비한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookmarkedStock:
    """종목 북마크 1건 — 알림 스캔의 축(누가 어떤 종목을 찜했나)."""

    user_id: int
    ticker: str   # 저장 키 그대로(대문자 정규화됨 — 005930.KS · AAPL)
    label: str    # 저장 시점 표시명 — 메일 본문 표기용


@dataclass(frozen=True)
class BookmarkedArea:
    """상권 북마크 1건 — 상권 알림 스캔의 축(B1)."""

    user_id: int
    trdar_code: int  # target_key(상권 코드 문자열)를 정수로 해석한 값
    label: str       # 저장 시점 상권 표시명
