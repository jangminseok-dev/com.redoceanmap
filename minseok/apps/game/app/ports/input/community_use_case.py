from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.community_dto import (
    DeleteCommand,
    PostReceipt,
    ReportCommand,
    ThreadQuery,
    ThreadView,
    WriteCommentCommand,
    WritePostCommand,
)


class CommunityUseCase(ABC):
    """종목 토론방 — 글·댓글 쓰기/읽기/본인 삭제/신고."""

    @abstractmethod
    async def thread(self, query: ThreadQuery) -> ThreadView:
        """종목의 최신 글과 각 글의 댓글. 지워졌거나 숨겨진 것은 나오지 않는다."""
        ...

    @abstractmethod
    async def write_post(self, command: WritePostCommand) -> PostReceipt:
        """글 작성. 없는 종목이면 UnknownSymbol, 빈 본문이면 InvalidPost."""
        ...

    @abstractmethod
    async def write_comment(self, command: WriteCommentCommand) -> PostReceipt:
        """댓글 작성. 대상 글이 없거나 내려갔으면 PostNotFound."""
        ...

    @abstractmethod
    async def delete_post(self, command: DeleteCommand) -> None:
        """본인 글 삭제. 남의 글이거나 이미 없으면 PostNotFound."""
        ...

    @abstractmethod
    async def delete_comment(self, command: DeleteCommand) -> None:
        """본인 댓글 삭제. 남의 댓글이거나 이미 없으면 PostNotFound."""
        ...

    @abstractmethod
    async def report(self, command: ReportCommand) -> None:
        """신고 접수(멱등 — 같은 사람이 같은 대상을 다시 신고해도 1건).

        접수만 한다. 내리는 판단은 어드민 몫이라 이 호출로 글이 사라지지 않는다.
        """
        ...
