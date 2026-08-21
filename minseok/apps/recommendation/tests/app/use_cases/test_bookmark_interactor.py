"""BookmarkInteractor — 정규화·멱등·상한·삭제 의미론을 스텁 포트로 검증."""
import pytest

from recommendation.app.dtos.bookmark_dto import BookmarkDraft
from recommendation.app.use_cases.bookmark_interactor import (
    MAX_BOOKMARKS,
    BookmarkInteractor,
    BookmarkLimitError,
)
from recommendation.domain.entities.bookmark_entity import Bookmark


class _StubRepo:
    def __init__(self, count: int = 0):
        self.count = count
        self.saved: list[Bookmark] = []
        self.deleted: list[tuple] = []
        self.delete_result = True

    async def upsert(self, bookmark):
        self.saved.append(bookmark)
        return Bookmark(
            id=1, user_id=bookmark.user_id, target_type=bookmark.target_type,
            target_key=bookmark.target_key, label=bookmark.label,
        )

    async def find_by_user(self, user_id):
        return self.saved

    async def count_by_user(self, user_id):
        return self.count

    async def delete(self, user_id, target_type, target_key):
        self.deleted.append((user_id, target_type, target_key))
        return self.delete_result


def _draft(target_type="stock", target_key="aapl", label=" 애플 ", user_id=7):
    return BookmarkDraft(
        user_id=user_id, target_type=target_type, target_key=target_key, label=label,
    )


async def test_종목_키는_대문자로_라벨은_공백을_정리해_저장한다():
    repo = _StubRepo()
    saved = await BookmarkInteractor(repo).add(_draft())
    assert repo.saved[0].target_key == "AAPL"
    assert repo.saved[0].label == "애플"
    assert saved.id == 1


async def test_라벨이_비면_키를_라벨로_쓴다():
    repo = _StubRepo()
    await BookmarkInteractor(repo).add(_draft(label="  "))
    assert repo.saved[0].label == "AAPL"


async def test_상권_키는_대소문자를_건드리지_않는다():
    repo = _StubRepo()
    await BookmarkInteractor(repo).add(_draft(target_type="area", target_key="3110008", label="성수동"))
    assert repo.saved[0].target_key == "3110008"


async def test_상한을_넘으면_등록을_거부한다():
    repo = _StubRepo(count=MAX_BOOKMARKS)
    with pytest.raises(BookmarkLimitError):
        await BookmarkInteractor(repo).add(_draft())
    assert repo.saved == []


async def test_잘못된_대상_종류는_ValueError():
    with pytest.raises(ValueError):
        await BookmarkInteractor(_StubRepo()).add(_draft(target_type="game"))


async def test_삭제는_종목_키를_같은_규칙으로_정규화한다():
    repo = _StubRepo()
    assert await BookmarkInteractor(repo).remove(7, "stock", " aapl ") is True
    assert repo.deleted == [(7, "stock", "AAPL")]


async def test_없는_것_삭제는_False지_오류가_아니다():
    repo = _StubRepo()
    repo.delete_result = False
    assert await BookmarkInteractor(repo).remove(7, "area", "999") is False
