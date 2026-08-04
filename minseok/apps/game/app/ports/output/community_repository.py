from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PostRecord:
    """글 1행. 작성자 이름은 담지 않는다 — user_id에서 유도한다(nickname)."""

    id: int
    user_id: int
    symbol: str
    body: str
    created_tick: int
    created_at: datetime


@dataclass(frozen=True)
class CommentRecord:

    id: int
    post_id: int
    user_id: int
    body: str
    created_tick: int
    created_at: datetime


class CommunityRepositoryPort(ABC):
    """토론방 저장소. 조회 메서드는 **내려간 것(본인 삭제·어드민 숨김)을 이미 걸러서** 준다 —
    필터를 유스케이스로 올리면 새 조회 경로가 생길 때마다 빠뜨릴 수 있다.
    """

    @abstractmethod
    async def list_posts(self, symbol: str, epoch_id: int, limit: int) -> list[PostRecord]:
        """종목의 최신 글(최신순)."""
        ...

    @abstractmethod
    async def list_comments(self, post_ids: list[int]) -> list[CommentRecord]:
        """여러 글의 댓글을 한 번에(오래된 순). 글마다 조회하면 N+1이 된다."""
        ...

    @abstractmethod
    async def find_post(self, post_id: int) -> PostRecord | None:
        """글 1건. 내려갔으면 None."""
        ...

    @abstractmethod
    async def add_post(
        self, user_id: int, symbol: str, epoch_id: int, body: str, tick: int
    ) -> PostRecord:
        ...

    @abstractmethod
    async def add_comment(
        self, user_id: int, post_id: int, epoch_id: int, body: str, tick: int
    ) -> CommentRecord:
        ...

    @abstractmethod
    async def soft_delete_post(self, user_id: int, post_id: int) -> bool:
        """본인 글만 지운다. 지운 게 없으면 False(남의 글·이미 없음 구분 없이)."""
        ...

    @abstractmethod
    async def soft_delete_comment(self, user_id: int, comment_id: int) -> bool:
        ...

    @abstractmethod
    async def add_report(
        self, reporter_user_id: int, target_type: str, target_id: int, reason: str
    ) -> None:
        """신고 접수. 같은 (대상, 신고자)면 조용히 넘어간다(멱등)."""
        ...

    @abstractmethod
    async def holders(self, symbol: str, user_ids: list[int], epoch_id: int) -> set[int]:
        """지금 이 종목의 **열린 포지션**을 가진 user_id들.

        '보유 중' 배지의 근거다. 작성 시점이 아니라 조회 시점 기준인 것이 중요하다 —
        글을 쓸 때 들고 있었는지가 아니라 지금 이해관계가 있는지를 보여주는 표시다.
        """
        ...
