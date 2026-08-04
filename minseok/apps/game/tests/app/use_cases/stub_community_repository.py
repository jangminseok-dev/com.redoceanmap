"""토론방 저장소 스텁 — mock 프레임워크 대신 실제로 동작하는 구현을 쓴다.

내려간 행 필터(본인 삭제·어드민 숨김)를 PG 리포지토리와 **같은 위치**에서 흉내낸다.
그래야 "유스케이스가 필터를 안 하는데 테스트는 통과"가 나오지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from game.app.ports.output.community_repository import (
    CommentRecord,
    CommunityRepositoryPort,
    PostRecord,
)

_BASE_TIME = datetime(2026, 8, 4, tzinfo=timezone.utc)


@dataclass
class _Row:
    id: int
    user_id: int
    body: str
    created_tick: int
    created_at: datetime
    symbol: str = ""
    post_id: int = 0
    deleted: bool = False
    hidden: bool = False

    @property
    def alive(self) -> bool:
        return not self.deleted and not self.hidden


@dataclass
class StubCommunityRepository(CommunityRepositoryPort):

    posts: list[_Row] = field(default_factory=list)
    comments: list[_Row] = field(default_factory=list)
    reports: list[tuple[int, str, int, str]] = field(default_factory=list)
    open_positions: set[tuple[str, int]] = field(default_factory=set)
    _seq: int = 0

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    def _stamp(self) -> datetime:
        # 순서가 보이도록 행마다 1초씩 민다 — 정렬 검증에 쓴다
        return _BASE_TIME + timedelta(seconds=self._seq)

    async def list_posts(self, symbol: str, epoch_id: int, limit: int) -> list[PostRecord]:
        rows = [p for p in self.posts if p.symbol == symbol and p.alive]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return [
            PostRecord(
                id=r.id,
                user_id=r.user_id,
                symbol=r.symbol,
                body=r.body,
                created_tick=r.created_tick,
                created_at=r.created_at,
            )
            for r in rows[:limit]
        ]

    async def list_comments(self, post_ids: list[int]) -> list[CommentRecord]:
        rows = [c for c in self.comments if c.post_id in post_ids and c.alive]
        rows.sort(key=lambda r: r.created_at)
        return [
            CommentRecord(
                id=r.id,
                post_id=r.post_id,
                user_id=r.user_id,
                body=r.body,
                created_tick=r.created_tick,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def find_post(self, post_id: int) -> PostRecord | None:
        row = next((p for p in self.posts if p.id == post_id and p.alive), None)
        if row is None:
            return None
        return PostRecord(
            id=row.id,
            user_id=row.user_id,
            symbol=row.symbol,
            body=row.body,
            created_tick=row.created_tick,
            created_at=row.created_at,
        )

    async def add_post(
        self, user_id: int, symbol: str, epoch_id: int, body: str, tick: int
    ) -> PostRecord:
        row = _Row(
            id=self._next_id(),
            user_id=user_id,
            body=body,
            created_tick=tick,
            created_at=self._stamp(),
            symbol=symbol,
        )
        self.posts.append(row)
        return PostRecord(
            id=row.id,
            user_id=user_id,
            symbol=symbol,
            body=body,
            created_tick=tick,
            created_at=row.created_at,
        )

    async def add_comment(
        self, user_id: int, post_id: int, epoch_id: int, body: str, tick: int
    ) -> CommentRecord:
        row = _Row(
            id=self._next_id(),
            user_id=user_id,
            body=body,
            created_tick=tick,
            created_at=self._stamp(),
            post_id=post_id,
        )
        self.comments.append(row)
        return CommentRecord(
            id=row.id,
            post_id=post_id,
            user_id=user_id,
            body=body,
            created_tick=tick,
            created_at=row.created_at,
        )

    async def soft_delete_post(self, user_id: int, post_id: int) -> bool:
        row = next(
            (p for p in self.posts if p.id == post_id and p.user_id == user_id and p.alive),
            None,
        )
        if row is None:
            return False
        row.deleted = True
        return True

    async def soft_delete_comment(self, user_id: int, comment_id: int) -> bool:
        row = next(
            (c for c in self.comments if c.id == comment_id and c.user_id == user_id and c.alive),
            None,
        )
        if row is None:
            return False
        row.deleted = True
        return True

    async def add_report(
        self, reporter_user_id: int, target_type: str, target_id: int, reason: str
    ) -> None:
        key = (reporter_user_id, target_type, target_id)
        if any(r[:3] == key for r in self.reports):
            return  # 유니크 제약을 흉내낸다
        self.reports.append((reporter_user_id, target_type, target_id, reason))

    async def holders(self, symbol: str, user_ids: list[int], epoch_id: int) -> set[int]:
        return {u for u in user_ids if (symbol, u) in self.open_positions}
