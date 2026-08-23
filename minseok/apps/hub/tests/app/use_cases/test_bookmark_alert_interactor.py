"""BookmarkAlertInteractor 테스트 — 스텁 포트로 조합·제외·dedupe 규칙을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from hub.app.dtos.alert_delivery_dto import DeliveredSignal
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


class _StubDeliveries:
    def __init__(self, previous: list[DeliveredSignal] | None = None):
        self.state = list(previous or [])
        self.replaced: list[list[DeliveredSignal]] = []

    async def last_signals(self) -> list[DeliveredSignal]:
        return list(self.state)

    async def replace(self, signals: list[DeliveredSignal]) -> None:
        self.replaced.append(list(signals))
        self.state = list(signals)


def _status(ticker: str, direction: str = "UP", ready: bool = False) -> StockStatusInfo:
    return StockStatusInfo(
        ticker=ticker, as_of=_NOW, direction=direction, price=100.0,
        change_pct=0.02, up_rate=None, baseline_up_rate=None,
        ready=ready, price_as_of=_NOW,
    )


def _build(bookmarks, statuses, emails, deliveries=None):
    return BookmarkAlertInteractor(
        bookmarks=_StubBookmarks(bookmarks),
        statuses=_StubStatuses(statuses),
        contacts=_StubContacts(emails),
        deliveries=deliveries or _StubDeliveries(),
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


async def test_북마크가_없으면_빈_리포트에_통지_상태도_비운다():
    statuses = _StubStatuses({})
    contacts = _StubContacts({})
    deliveries = _StubDeliveries(previous=[DeliveredSignal(1, "AAPL", "UP")])
    interactor = BookmarkAlertInteractor(
        bookmarks=_StubBookmarks([]), statuses=statuses, contacts=contacts,
        deliveries=deliveries,
    )
    report = await interactor.scan()
    assert report.emails == [] and report.bookmarks_scanned == 0
    assert statuses.calls == [] and contacts.calls == []
    assert deliveries.state == []  # 잔존 상태가 훗날 첫 알림을 삼키지 않게


async def test_신호가_전부_중립이면_연락처_조회조차_하지_않는다():
    contacts = _StubContacts({1: "a@x.com"})
    interactor = BookmarkAlertInteractor(
        bookmarks=_StubBookmarks([BookmarkedStock(user_id=1, ticker="TSLA", label="테슬라")]),
        statuses=_StubStatuses({"TSLA": _status("TSLA", "NEUTRAL")}),
        contacts=contacts,
        deliveries=_StubDeliveries(),
    )
    report = await interactor.scan()
    assert report.emails == [] and report.signals_found == 0
    assert contacts.calls == []


# --- dedupe — 같은 신호 반복 발송 방지 ---

async def test_같은_신호가_지속되면_발송을_억제하고_상태는_유지한다():
    deliveries = _StubDeliveries(previous=[DeliveredSignal(1, "AAPL", "UP")])
    interactor = _build(
        [BookmarkedStock(user_id=1, ticker="AAPL", label="애플")],
        {"AAPL": _status("AAPL", "UP")}, {1: "a@x.com"}, deliveries,
    )
    report = await interactor.scan()
    assert report.emails == [] and report.deduped == 1 and report.signals_found == 1
    assert deliveries.state == [DeliveredSignal(1, "AAPL", "UP")]  # 다음 스캔에도 억제


async def test_방향이_바뀌면_새_알림이_나가고_상태가_갱신된다():
    deliveries = _StubDeliveries(previous=[DeliveredSignal(1, "AAPL", "UP")])
    interactor = _build(
        [BookmarkedStock(user_id=1, ticker="AAPL", label="애플")],
        {"AAPL": _status("AAPL", "DOWN")}, {1: "a@x.com"}, deliveries,
    )
    report = await interactor.scan()
    assert len(report.emails) == 1 and "하락" in report.emails[0].subject
    assert deliveries.state == [DeliveredSignal(1, "AAPL", "DOWN")]


async def test_신호가_꺼지면_상태가_사라져_재발생_때_새_알림이다():
    deliveries = _StubDeliveries(previous=[DeliveredSignal(1, "AAPL", "UP")])
    interactor = _build(
        [BookmarkedStock(user_id=1, ticker="AAPL", label="애플")],
        {"AAPL": _status("AAPL", "NEUTRAL")}, {1: "a@x.com"}, deliveries,
    )
    await interactor.scan()
    assert deliveries.state == []  # 소멸 반영

    # 다음 스캔에서 같은 방향이 재발생 — dedupe 없이 발송된다
    interactor2 = _build(
        [BookmarkedStock(user_id=1, ticker="AAPL", label="애플")],
        {"AAPL": _status("AAPL", "UP")}, {1: "a@x.com"}, deliveries,
    )
    report = await interactor2.scan()
    assert len(report.emails) == 1


async def test_이메일_없어_못_보낸_신호는_상태에_남기지_않는다():
    deliveries = _StubDeliveries()
    interactor = _build(
        [BookmarkedStock(user_id=1, ticker="AAPL", label="애플")],
        {"AAPL": _status("AAPL", "UP")}, {}, deliveries,  # 이메일 없음
    )
    report = await interactor.scan()
    assert report.emails == []
    assert deliveries.state == []  # 이메일이 생기면 그때 첫 알림이 나가야 한다
