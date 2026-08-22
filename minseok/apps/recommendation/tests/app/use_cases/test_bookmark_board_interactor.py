"""BookmarkBoardInteractor 테스트 — 스텁 포트로 격리·열화·정렬을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from hub.app.dtos.commercial_data_dto import AreaScoreComponent, AreaScoreInfo
from hub.app.dtos.stock_status_dto import StockStatusInfo
from recommendation.app.use_cases.bookmark_board_interactor import BookmarkBoardInteractor
from recommendation.domain.entities.bookmark_entity import Bookmark

_NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


class _StubBookmarks:
    """find_by_user는 실제 리포지토리처럼 해당 사용자 것만, 등록 최신순으로 준다."""

    def __init__(self, rows: list[Bookmark]) -> None:
        self._rows = rows

    async def find_by_user(self, user_id: int) -> list[Bookmark]:
        mine = [b for b in self._rows if b.user_id == user_id]
        return sorted(mine, key=lambda b: (b.created_at, b.id), reverse=True)


class _StubStockStatuses:
    def __init__(self, statuses: dict[str, StockStatusInfo] | None = None, fail: bool = False):
        self.statuses = statuses or {}
        self.fail = fail
        self.calls: list[list[str]] = []

    async def latest_statuses(self, symbols: list[str]) -> dict[str, StockStatusInfo]:
        self.calls.append(list(symbols))
        if self.fail:
            raise RuntimeError("스냅샷 저장소 불가")
        return {s: v for s, v in self.statuses.items() if s in symbols}


class _StubMarket:
    def __init__(self, scores: dict[int, AreaScoreInfo] | None = None, fail: bool = False):
        self.scores = scores or {}
        self.fail = fail
        self.calls: list[list[int]] = []

    async def get_area_scores(self, trdar_codes: list[int]) -> dict[int, AreaScoreInfo]:
        self.calls.append(list(trdar_codes))
        if self.fail:
            raise RuntimeError("점수 조회 불가")
        return {c: v for c, v in self.scores.items() if c in trdar_codes}


def _bm(id: int, user_id: int, target_type: str, target_key: str,
        created_at: datetime = _NOW) -> Bookmark:
    return Bookmark(id=id, user_id=user_id, target_type=target_type,
                    target_key=target_key, label=target_key, created_at=created_at)


def _status(ticker: str = "AAPL") -> StockStatusInfo:
    return StockStatusInfo(
        ticker=ticker, as_of=_NOW, direction="UP", price=230.0, change_pct=0.012,
        up_rate=0.61, baseline_up_rate=0.55, ready=True, price_as_of=_NOW,
    )


def _score() -> AreaScoreInfo:
    return AreaScoreInfo(
        total=62.0, grade="양호",
        components=(
            AreaScoreComponent(key="sales_growth", name="매출 성장",
                               score=70.0, value=3.2, benchmark=1.1),
        ),
    )


async def test_격리_내_북마크만_보드에_실린다():
    rows = [
        _bm(1, user_id=7, target_type="stock", target_key="AAPL"),
        _bm(2, user_id=8, target_type="stock", target_key="TSLA"),   # 남의 것
        _bm(3, user_id=8, target_type="area", target_key="1000001"),  # 남의 것
    ]
    statuses = _StubStockStatuses({"AAPL": _status(), "TSLA": _status("TSLA")})
    interactor = BookmarkBoardInteractor(
        bookmarks=_StubBookmarks(rows), stock_statuses=statuses, market=_StubMarket(),
    )
    items = await interactor.board(7)
    assert [i.bookmark.id for i in items] == [1]
    # 상태 조회 자체가 남의 키를 포함하지 않는다 — 응답 필터가 아니라 조회 범위의 격리
    assert statuses.calls == [["AAPL"]]


async def test_종목_상권_상태가_각자_붙고_정렬은_등록_최신순이다():
    old = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = [
        _bm(1, 7, "stock", "AAPL", created_at=old),
        _bm(2, 7, "area", "1000001", created_at=_NOW),
    ]
    interactor = BookmarkBoardInteractor(
        bookmarks=_StubBookmarks(rows),
        stock_statuses=_StubStockStatuses({"AAPL": _status()}),
        market=_StubMarket({1000001: _score()}),
    )
    items = await interactor.board(7)
    assert [i.bookmark.id for i in items] == [2, 1]  # 최신 등록(상권)이 먼저
    assert items[0].area is not None and items[0].area.total == 62.0
    assert items[1].stock is not None and items[1].stock.direction == "UP"


async def test_열화_상태_없는_항목과_포트_실패에도_목록은_뜬다():
    rows = [
        _bm(1, 7, "stock", "NOSNAP"),      # 스냅샷 없는 종목
        _bm(2, 7, "area", "1000001"),
    ]
    # 종목 상태 포트가 통째로 실패해도 보드는 나간다
    interactor = BookmarkBoardInteractor(
        bookmarks=_StubBookmarks(rows),
        stock_statuses=_StubStockStatuses(fail=True),
        market=_StubMarket(fail=True),
    )
    items = await interactor.board(7)
    assert len(items) == 2
    assert all(i.stock is None and i.area is None for i in items)


async def test_북마크_0건이면_빈_보드_포트_호출_없음():
    statuses = _StubStockStatuses()
    market = _StubMarket()
    interactor = BookmarkBoardInteractor(
        bookmarks=_StubBookmarks([]), stock_statuses=statuses, market=market,
    )
    assert await interactor.board(7) == []
    assert statuses.calls == [] and market.calls == []
