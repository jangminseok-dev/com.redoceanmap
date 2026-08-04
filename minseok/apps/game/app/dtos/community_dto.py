from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ThreadQuery:
    """종목 토론방 열기. `viewer_user_id`는 '내 글인가'·'보유 중인가' 판정에 쓴다."""

    symbol: str
    viewer_user_id: int
    limit: int = 20


@dataclass(frozen=True)
class WritePostCommand:
    user_id: int
    symbol: str
    body: str


@dataclass(frozen=True)
class WriteCommentCommand:
    user_id: int
    post_id: int
    body: str


@dataclass(frozen=True)
class DeleteCommand:
    """본인 삭제 — 남의 글은 지울 수 없다(유스케이스가 작성자 일치를 확인한다)."""

    user_id: int
    target_id: int


@dataclass(frozen=True)
class ReportCommand:
    reporter_user_id: int
    target_type: str  # post | comment
    target_id: int
    reason: str


@dataclass(frozen=True)
class CommentView:
    id: int
    author: str                 # 결정론 가명 — 실명이 아니다
    body: str
    created_tick: int
    created_at: datetime
    mine: bool                  # 조회자 본인이 쓴 댓글 — 삭제 버튼이 붙는 자리
    holds_symbol: bool          # 작성 시점이 아니라 **지금** 이 종목을 들고 있는가


@dataclass(frozen=True)
class PostView:
    id: int
    author: str
    body: str
    created_tick: int
    created_at: datetime
    mine: bool
    holds_symbol: bool
    comments: tuple[CommentView, ...]


@dataclass(frozen=True)
class ThreadView:
    symbol: str
    name: str                   # 가상 회사명
    posts: tuple[PostView, ...]


@dataclass(frozen=True)
class PostReceipt:
    id: int
    created_tick: int
