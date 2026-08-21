from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# 북마크 대상 종류 — 종목(ticker)과 상권(trdar_code). 새 종류는 화면·딥링크가 함께 생길 때만.
TARGET_TYPES = ("stock", "area")


@dataclass(frozen=True)
class Bookmark:
    """사용자 북마크 1건 — 사용자 ↔ 분석 대상(종목/상권)의 연결.

    추천 기록(Recommendation)과 같은 성격의 연결이라 이 스포크가 소유한다(ROADMAP 판정:
    CRUD 2~3개짜리 새 스포크는 과설계). label은 저장 시점 표시명 — 대상 이름이 나중에
    바뀌어도 목록이 "무엇을 찜했는지"를 계속 읽을 수 있게 동결한다.
    """

    user_id: int
    target_type: str          # stock | area
    target_key: str           # 종목 심볼(대문자) 또는 상권 코드 문자열
    label: str
    created_at: datetime | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.user_id <= 0:
            raise ValueError("Bookmark은 user_id가 필수입니다.")
        if self.target_type not in TARGET_TYPES:
            raise ValueError(f"target_type은 {TARGET_TYPES} 중 하나여야 합니다: {self.target_type}")
        if not self.target_key.strip():
            raise ValueError("Bookmark은 target_key가 필수입니다.")
