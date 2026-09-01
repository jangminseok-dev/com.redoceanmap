"""PriceAlertInteractor 테스트 — 스텁 저장소로 검증·상한·정규화 규칙을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert
from recommendation.app.use_cases.price_alert_interactor import (
    MAX_ACTIVE_ALERTS,
    PriceAlertInteractor,
    PriceAlertLimitError,
)

_NOW = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


class _StubRepo:
    def __init__(self, active_count: int = 0):
        self.active_count = active_count
        self.added: list[PriceAlertDraft] = []
        self.deleted: list[tuple[int, int]] = []

    async def list_by_user(self, user_id: int):
        return []

    async def count_active(self, user_id: int) -> int:
        return self.active_count

    async def add(self, draft: PriceAlertDraft) -> StoredPriceAlert:
        self.added.append(draft)
        return StoredPriceAlert(
            id=1, ticker=draft.ticker, target_price=draft.target_price,
            direction=draft.direction, active=True, triggered_at=None, created_at=_NOW,
        )

    async def delete(self, user_id: int, alert_id: int) -> bool:
        self.deleted.append((user_id, alert_id))
        return True


def _draft(**overrides) -> PriceAlertDraft:
    base = dict(user_id=1, ticker="aapl", target_price=200.0, direction="below")
    return PriceAlertDraft(**{**base, **overrides})


async def test_등록은_티커를_대문자_정규화한다():  # 북마크 stock 규칙과 동일
    repo = _StubRepo()
    stored = await PriceAlertInteractor(alerts=repo).create(_draft(ticker=" aapl "))
    assert stored.ticker == "AAPL" and repo.added[0].ticker == "AAPL"


async def test_방향_어휘와_가격을_검증한다():
    interactor = PriceAlertInteractor(alerts=_StubRepo())
    with pytest.raises(ValueError):
        await interactor.create(_draft(direction="up"))
    with pytest.raises(ValueError):
        await interactor.create(_draft(target_price=0))
    with pytest.raises(ValueError):
        await interactor.create(_draft(ticker="  "))


async def test_활성_상한_초과는_거절한다():
    interactor = PriceAlertInteractor(alerts=_StubRepo(active_count=MAX_ACTIVE_ALERTS))
    with pytest.raises(PriceAlertLimitError):
        await interactor.create(_draft())


async def test_삭제는_소유_판정을_저장소에_위임한다():
    repo = _StubRepo()
    assert await PriceAlertInteractor(alerts=repo).remove(1, 7) is True
    assert repo.deleted == [(1, 7)]
