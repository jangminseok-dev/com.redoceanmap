import pytest

from game.app.dtos.community_dto import (
    DeleteCommand,
    ReportCommand,
    ThreadQuery,
    WriteCommentCommand,
    WritePostCommand,
)
from game.app.exceptions import InvalidPost, PostNotFound, UnknownSymbol
from game.app.use_cases.community_interactor import MAX_BODY_LENGTH, CommunityInteractor
from game.domain.community.nickname import display_name
from game.domain.market.symbol_params import SYMBOLS
from game.tests.app.use_cases.stub_community_repository import StubCommunityRepository

SYMBOL = SYMBOLS[0].symbol
OTHER_SYMBOL = SYMBOLS[1].symbol


class _StubClock:
    def __init__(self, tick: int = 1_000):
        self._tick = tick

    def now_tick(self) -> int:
        return self._tick


def _interactor(repo=None, tick: int = 1_000):
    return CommunityInteractor(repository=repo or StubCommunityRepository(), clock=_StubClock(tick))


async def test_글을_쓰고_토론방에서_읽는다():
    repo = StubCommunityRepository()
    it = _interactor(repo)

    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="이 종목 어떻게 보세요?"))
    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))

    assert len(view.posts) == 1
    assert view.posts[0].body == "이 종목 어떻게 보세요?"
    assert view.posts[0].mine is True


async def test_작성자는_실명이_아니라_결정론_가명으로_나온다():
    """users.name을 띄우면 게임 참여가 곧 실명 공개가 된다."""
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="안녕하세요"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=99))

    assert view.posts[0].author == display_name(7)
    # 같은 사람이 다시 써도 같은 이름이어야 한다
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="하나 더"))
    again = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=99))
    assert {p.author for p in again.posts} == {display_name(7)}


async def test_남이_쓴_글은_mine이_아니다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="내 글"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=8))
    assert view.posts[0].mine is False


async def test_보유_중인_작성자에게_배지가_붙는다():
    """작성 시점이 아니라 **지금** 열린 포지션이 있는가로 판정한다."""
    repo = StubCommunityRepository()
    repo.open_positions.add((SYMBOL, 7))
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="들고 있습니다"))
    await it.write_post(WritePostCommand(user_id=8, symbol=SYMBOL, body="저는 없습니다"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=1))
    by_author = {p.author: p.holds_symbol for p in view.posts}

    assert by_author[display_name(7)] is True
    assert by_author[display_name(8)] is False


async def test_다른_종목의_포지션은_배지를_만들지_않는다():
    repo = StubCommunityRepository()
    repo.open_positions.add((OTHER_SYMBOL, 7))
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="글"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=1))
    assert view.posts[0].holds_symbol is False


async def test_댓글은_글에_묶여_나온다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    post = await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="질문"))
    await it.write_comment(WriteCommentCommand(user_id=8, post_id=post.id, body="답변"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=8))

    assert len(view.posts[0].comments) == 1
    assert view.posts[0].comments[0].body == "답변"
    assert view.posts[0].comments[0].mine is True


async def test_없는_글에는_댓글을_달_수_없다():
    it = _interactor()
    with pytest.raises(PostNotFound):
        await it.write_comment(WriteCommentCommand(user_id=8, post_id=999, body="답변"))


async def test_본인_글은_지울_수_있고_목록에서_사라진다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    post = await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="지울 글"))

    await it.delete_post(DeleteCommand(user_id=7, target_id=post.id))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert view.posts == ()


async def test_남의_글은_지울_수_없다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    post = await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="내 글"))

    with pytest.raises(PostNotFound):
        await it.delete_post(DeleteCommand(user_id=8, target_id=post.id))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert len(view.posts) == 1  # 그대로 남아 있다


async def test_어드민이_숨긴_글은_목록에_나오지_않는다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="문제 글"))
    repo.posts[0].hidden = True

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert view.posts == ()


async def test_숨겨진_글의_댓글도_함께_사라진다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    post = await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="글"))
    await it.write_comment(WriteCommentCommand(user_id=8, post_id=post.id, body="댓글"))
    repo.posts[0].hidden = True

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=8))
    assert view.posts == ()


async def test_신고는_접수만_하고_글을_내리지_않는다():
    """여럿이 몰려 신고하는 것만으로 남의 글이 내려가면 안 된다."""
    repo = StubCommunityRepository()
    it = _interactor(repo)
    post = await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="글"))

    await it.report(
        ReportCommand(reporter_user_id=8, target_type="post", target_id=post.id, reason="욕설")
    )

    assert len(repo.reports) == 1
    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert len(view.posts) == 1  # 그대로 보인다


async def test_같은_사람의_반복_신고는_한_건이다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    for _ in range(3):
        await it.report(
            ReportCommand(reporter_user_id=8, target_type="post", target_id=1, reason="욕설")
        )
    assert len(repo.reports) == 1


async def test_다른_사람의_신고는_따로_쌓인다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.report(
        ReportCommand(reporter_user_id=8, target_type="post", target_id=1, reason="욕설")
    )
    await it.report(
        ReportCommand(reporter_user_id=9, target_type="post", target_id=1, reason="광고")
    )
    assert len(repo.reports) == 2


@pytest.mark.parametrize("target_type", ["user", "", "POST", "글"])
async def test_알_수_없는_신고_대상은_거부한다(target_type):
    it = _interactor()
    with pytest.raises(InvalidPost):
        await it.report(
            ReportCommand(
                reporter_user_id=8, target_type=target_type, target_id=1, reason="욕설"
            )
        )


@pytest.mark.parametrize("body", ["", "   ", "\n\t "])
async def test_빈_본문은_거부한다(body):
    it = _interactor()
    with pytest.raises(InvalidPost):
        await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body=body))


async def test_상한을_넘는_본문은_거부한다():
    it = _interactor()
    with pytest.raises(InvalidPost):
        await it.write_post(
            WritePostCommand(user_id=7, symbol=SYMBOL, body="가" * (MAX_BODY_LENGTH + 1))
        )


async def test_없는_종목의_토론방은_거부한다():
    it = _interactor()
    with pytest.raises(UnknownSymbol):
        await it.thread(ThreadQuery(symbol="ZZ99", viewer_user_id=7))
    with pytest.raises(UnknownSymbol):
        await it.write_post(WritePostCommand(user_id=7, symbol="ZZ99", body="글"))


async def test_다른_종목의_글은_섞이지_않는다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="이쪽"))
    await it.write_post(WritePostCommand(user_id=7, symbol=OTHER_SYMBOL, body="저쪽"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert [p.body for p in view.posts] == ["이쪽"]


async def test_최신_글이_먼저_나온다():
    repo = StubCommunityRepository()
    it = _interactor(repo)
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="먼저"))
    await it.write_post(WritePostCommand(user_id=7, symbol=SYMBOL, body="나중"))

    view = await it.thread(ThreadQuery(symbol=SYMBOL, viewer_user_id=7))
    assert [p.body for p in view.posts] == ["나중", "먼저"]
