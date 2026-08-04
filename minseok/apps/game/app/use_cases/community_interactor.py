from __future__ import annotations

from game.app.dtos.community_dto import (
    CommentView,
    DeleteCommand,
    PostReceipt,
    PostView,
    ReportCommand,
    ThreadQuery,
    ThreadView,
    WriteCommentCommand,
    WritePostCommand,
)
from game.app.exceptions import InvalidPost, PostNotFound, UnknownSymbol
from game.app.ports.input.community_use_case import CommunityUseCase
from game.app.ports.output.community_repository import CommunityRepositoryPort
from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import GAME_EPOCH_ID, SEASON_TICKS
from game.domain.community.nickname import display_name
from game.domain.market.symbol_params import SYMBOLS

MAX_BODY_LENGTH = 1_000   # 토론방 한 글의 상한. 길어지면 목록이 읽히지 않는다
MAX_POSTS = 50            # 한 번에 내려보내는 글 수 상한
MAX_REASON_LENGTH = 200   # 신고 사유 — ORM 컬럼과 같은 값
TARGET_TYPES = ("post", "comment")


class CommunityInteractor(CommunityUseCase):
    """종목 토론방 대장.

    **저장하는 슬라이스다.** 게임의 다른 값은 시각의 함수라 저장하지 않지만(harness §1-A)
    사람이 쓴 문장은 유도할 수 없다. 대신 작성자 이름은 저장하지 않고 user_id에서
    결정론으로 만든다 — 실명이 새지 않고, 같은 사람의 글이 항상 같은 이름을 갖는다.

    **신고가 글을 내리지 않는다.** 접수만 하고 판단은 어드민이 한다.
    """

    def __init__(self, repository: CommunityRepositoryPort, clock: GameClockPort) -> None:
        self._repository = repository
        self._clock = clock

    async def thread(self, query: ThreadQuery) -> ThreadView:
        params = _find_symbol(query.symbol)
        limit = max(1, min(query.limit, MAX_POSTS))
        posts = await self._repository.list_posts(params.symbol, GAME_EPOCH_ID, limit)
        comments = (
            await self._repository.list_comments([p.id for p in posts]) if posts else []
        )

        # '보유 중' 배지는 글·댓글 작성자 전원을 한 번에 조회한다 — 작성자마다 물으면 N+1이다
        authors = {p.user_id for p in posts} | {c.user_id for c in comments}
        holding = (
            await self._repository.holders(params.symbol, sorted(authors), GAME_EPOCH_ID)
            if authors
            else set()
        )

        by_post: dict[int, list[CommentView]] = {}
        for c in comments:
            by_post.setdefault(c.post_id, []).append(
                CommentView(
                    id=c.id,
                    author=display_name(c.user_id),
                    body=c.body,
                    created_tick=c.created_tick,
                    created_at=c.created_at,
                    mine=c.user_id == query.viewer_user_id,
                    holds_symbol=c.user_id in holding,
                )
            )

        return ThreadView(
            symbol=params.symbol,
            name=params.name,
            posts=tuple(
                PostView(
                    id=p.id,
                    author=display_name(p.user_id),
                    body=p.body,
                    created_tick=p.created_tick,
                    created_at=p.created_at,
                    mine=p.user_id == query.viewer_user_id,
                    holds_symbol=p.user_id in holding,
                    comments=tuple(by_post.get(p.id, ())),
                )
                for p in posts
            ),
        )

    async def write_post(self, command: WritePostCommand) -> PostReceipt:
        params = _find_symbol(command.symbol)
        body = _clean_body(command.body)
        record = await self._repository.add_post(
            user_id=command.user_id,
            symbol=params.symbol,
            epoch_id=GAME_EPOCH_ID,
            body=body,
            tick=self._now_tick(),
        )
        return PostReceipt(id=record.id, created_tick=record.created_tick)

    async def write_comment(self, command: WriteCommentCommand) -> PostReceipt:
        body = _clean_body(command.body)
        if await self._repository.find_post(command.post_id) is None:
            raise PostNotFound("글이 없거나 이미 내려갔습니다")
        record = await self._repository.add_comment(
            user_id=command.user_id,
            post_id=command.post_id,
            epoch_id=GAME_EPOCH_ID,
            body=body,
            tick=self._now_tick(),
        )
        return PostReceipt(id=record.id, created_tick=record.created_tick)

    async def delete_post(self, command: DeleteCommand) -> None:
        if not await self._repository.soft_delete_post(command.user_id, command.target_id):
            raise PostNotFound("글이 없거나 이미 내려갔습니다")

    async def delete_comment(self, command: DeleteCommand) -> None:
        if not await self._repository.soft_delete_comment(command.user_id, command.target_id):
            raise PostNotFound("댓글이 없거나 이미 내려갔습니다")

    async def report(self, command: ReportCommand) -> None:
        if command.target_type not in TARGET_TYPES:
            raise InvalidPost(f"신고 대상은 {' 또는 '.join(TARGET_TYPES)}여야 합니다")
        reason = command.reason.strip()
        if not reason:
            raise InvalidPost("신고 사유를 적어주세요")
        await self._repository.add_report(
            reporter_user_id=command.reporter_user_id,
            target_type=command.target_type,
            target_id=command.target_id,
            reason=reason[:MAX_REASON_LENGTH],
        )

    def _now_tick(self) -> int:
        """시즌이 끝나도 글은 쓸 수 있다 — 매매와 달리 기록이 닫힐 이유가 없다.

        다만 틱은 마지막 틱에 멈춘다(미래 틱을 만들지 않는다, harness §1-6).
        """
        return min(self._clock.now_tick(), SEASON_TICKS)


def _find_symbol(symbol: str):
    params = next((s for s in SYMBOLS if s.symbol == symbol), None)
    if params is None:
        raise UnknownSymbol(f"알 수 없는 종목입니다: {symbol}")
    return params


def _clean_body(body: str) -> str:
    cleaned = body.strip()
    if not cleaned:
        raise InvalidPost("내용을 입력해주세요")
    if len(cleaned) > MAX_BODY_LENGTH:
        raise InvalidPost(f"{MAX_BODY_LENGTH}자까지 쓸 수 있습니다")
    return cleaned
