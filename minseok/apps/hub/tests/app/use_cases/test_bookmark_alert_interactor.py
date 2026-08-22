"""BookmarkAlertInteractor 테스트 — 스텁 포트로 조합·제외 규칙을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from hub.app.dtos.bookmark_directory_dto import BookmarkedStock
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.use_cases.bookmark_alert_interactor import BookmarkAlertInteractor

_NOW = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)


class _StubBookmarks:
    def __init__(self, rows: list[BookmarkedStock]):
        self.rows = rows

    async def stock_bookmarks(self) -> list[BookmarkedStock]:
        return self.rows


class _StubStatuses:
    def __init__(self, statuses: dict[str, StockStatusInfo]):
        self.statuses = statuses
        self.calls: list[list[str]] = []

    async def latest_statuses(self, symbols: list[str]) -> dict[str, StockStatusInfo]:
        self.calls.append(list(symbols))
        return {s: v for s, v in self.statuses.items() if s in symbols}


class _StubContacts:
    def __init__(self, emails: dict[int, str]):
        self.emails = emails
        self.calls: list[list[int]] = []

    async def emails_by_ids(self, user_ids: list[int]) -> dict[int, str]:
        self.calls.append(list(user_ids))
        return {u: e for u, e in self.emails.items() if u in user_ids}


def _status(ticker: str, direction: str = "UP", ready: bool = False) -> StockStatusInfo:
    return StockStatusInfo(
        ticker=ticker, as_of=_NOW, direction=direction, price=100.0,
        change_pct=0.02, up_rate=None, baseline_up_rate=None,
        ready=ready, price_as_of=_NOW,
    )


def _build(bookmarks, statuses, emails):
    return BookmarkAlertInteractor(
        bookmarks=_StubBookmarks(bookmarks),
        statuses=_StubStatuses(statuses),
        contacts=_StubContacts(emails),
    )


async def test_비중립_신호만_사용자별_메일로_묶인다():
    bookmarks = [
        BookmarkedStock(user_id=1, ticker="AAPL", label="애플"),
        BookmarkedStock(user_id=1, ticker="TSLA", label="테슬라"),   # 중립 — 제외
        BookmarkedStock(user_id=2, ticker="AAPL", label="애플"),
        BookmarkedStock(user_id=2, ticker="NOSNAP", label="스냅샷없음"),  # 상태 없음 — 제외
    ]
    statuses = {"AAPL": _status("AAPL", "UP", ready=True), "TSLA": _status("TSLA", "NEUTRAL")}
    interactor = _build(bookmarks, statuses, {1: "a@x.com", 2: "b@x.com"})
    report = await interactor.scan()

    assert (report.bookmarks_scanned, report.symbols_scanned) == (4, 3)
    assert report.signals_found == 2  # (user1, AAPL) + (user2, AAPL)
    assert [e.to for e in report.emails] == ["a@x.com", "b@x.com"]
    assert "신호 1건" in report.emails[0].subject
    assert "애플(AAPL)" in report.emails[0].body and "검증 참고 신호" in report.emails[0].body


async def test_이메일_없는_사용자는_발송에서_빠지고_나머지는_유지된다():
    bookmarks = [
        BookmarkedStock(user_id=1, ticker="AAPL", label="애플"),
        BookmarkedStock(user_id=2, ticker="AAPL", label="애플"),  # 탈퇴·이메일 없음
    ]
    interactor = _build(bookmarks, {"AAPL": _status("AAPL")}, {1: "a@x.com"})
    report = await interactor.scan()
    assert [e.to for e in report.emails] == ["a@x.com"]
    assert report.signals_found == 2  # 관측 자체는 집계에 남는다


async def test_북마크가_없으면_포트_호출_없이_빈_리포트():
    statuses = _StubStatuses({})
    contacts = _StubContacts({})
    interactor = BookmarkAlertInteractor(
        bookmarks=_StubBookmarks([]), statuses=statuses, contacts=contacts,
    )
    report = await interactor.scan()
    assert report.emails == [] and report.bookmarks_scanned == 0
    assert statuses.calls == [] and contacts.calls == []


async def test_신호가_전부_중립이면_연락처_조회조차_하지_않는다():
    contacts = _StubContacts({1: "a@x.com"})
    interactor = BookmarkAlertInteractor(
        bookmarks=_StubBookmarks([BookmarkedStock(user_id=1, ticker="TSLA", label="테슬라")]),
        statuses=_StubStatuses({"TSLA": _status("TSLA", "NEUTRAL")}),
        contacts=contacts,
    )
    report = await interactor.scan()
    assert report.emails == [] and report.signals_found == 0
    assert contacts.calls == []
