from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReportedRecord:
    """신고가 쌓인 글·댓글 1건 — 어드민 검토 대기줄의 한 줄."""

    target_type: str            # post | comment
    target_id: int
    symbol: str                 # 댓글이면 달린 글의 종목
    author_user_id: int         # 표시 이름은 소비자가 nickname으로 만든다
    body: str
    report_count: int
    reasons: tuple[str, ...]    # 신고 사유들 — 중복 제거하지 않는다(빈도가 곧 신호)
    reported_at: datetime       # 가장 최근 신고 시각 — 대기줄 정렬 축
    hidden: bool                # 이미 내려간 것도 보여준다(되돌리려면 보여야 한다)


class CommunityModerationRepositoryPort(ABC):
    """토론방 운영 저장소 — **어드민만 쓴다.**

    사용자용 `CommunityRepositoryPort`와 나눈 이유: 소비자가 다르다. 한 포트에 두면
    사용자 슬라이스의 테스트 스텁이 어드민 기능이 늘 때마다 흔들린다
    (허브 `AreaDemandProfilePort`를 기존 포트 확장이 아니라 신설한 것과 같은 근거).
    """

    @abstractmethod
    async def list_reported(self, limit: int) -> list[ReportedRecord]:
        """신고가 1건 이상 쌓인 글·댓글(최근 신고순)."""
        ...

    @abstractmethod
    async def hide(self, target_type: str, target_id: int, reason: str) -> bool:
        """글·댓글을 내린다. 이미 내려갔거나 없으면 False.

        작성자 본인 삭제(`deleted_at`)와 **다른 컬럼**에 쓴다 — 누가 왜 내렸는지가 남아야 한다.
        """
        ...

    @abstractmethod
    async def unhide(self, target_type: str, target_id: int) -> bool:
        """숨김 해제. 본인이 지운 글은 되살리지 않는다(작성자 의사가 우선)."""
        ...
