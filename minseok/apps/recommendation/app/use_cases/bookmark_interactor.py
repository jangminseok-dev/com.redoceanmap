from __future__ import annotations

import logging

from recommendation.app.dtos.bookmark_dto import BookmarkDraft
from recommendation.app.ports.input.bookmark_use_case import BookmarkUseCase
from recommendation.app.ports.output.bookmark_repository import BookmarkRepositoryPort
from recommendation.domain.entities.bookmark_entity import Bookmark

logger = logging.getLogger(__name__)

# 사용자당 상한 — UI(목록 화면)가 감당할 수준이자 무한 적재 방어. 도달하면 오래된 것을
# 지우라고 안내한다(자동 삭제는 사용자 데이터를 조용히 버리는 일이라 하지 않는다).
MAX_BOOKMARKS = 200


class BookmarkLimitError(Exception):
    """사용자당 북마크 상한 초과."""


class BookmarkInteractor(BookmarkUseCase):
    """북마크 대장 — 정규화·상한 검사 후 영속에 위임한다."""

    def __init__(self, bookmarks: BookmarkRepositoryPort) -> None:
        self._bookmarks = bookmarks

    async def add(self, draft: BookmarkDraft) -> Bookmark:
        key = draft.target_key.strip()
        if draft.target_type == "stock":
            key = key.upper()  # 종목은 대소문자 표기가 섞여 들어온다(aapl ↔ AAPL) — 정본은 대문자
        bookmark = Bookmark(
            user_id=draft.user_id,
            target_type=draft.target_type,
            target_key=key,
            label=draft.label.strip() or key,
        )
        if await self._bookmarks.count_by_user(draft.user_id) >= MAX_BOOKMARKS:
            raise BookmarkLimitError(
                f"북마크는 {MAX_BOOKMARKS}개까지 저장할 수 있습니다. 오래된 항목을 지워 주세요."
            )
        saved = await self._bookmarks.upsert(bookmark)
        logger.info("[bookmark] user=%d %s:%s 등록", draft.user_id, saved.target_type, saved.target_key)
        return saved

    async def list_mine(self, user_id: int) -> list[Bookmark]:
        return await self._bookmarks.find_by_user(user_id)

    async def remove(self, user_id: int, target_type: str, target_key: str) -> bool:
        key = target_key.strip().upper() if target_type == "stock" else target_key.strip()
        deleted = await self._bookmarks.delete(user_id, target_type, key)
        logger.info("[bookmark] user=%d %s:%s 삭제(%s)", user_id, target_type, key, deleted)
        return deleted
