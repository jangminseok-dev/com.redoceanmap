"""NewsAlertScanInteractor 테스트 — 스텁 포트로 매칭·접미 흡수·신호 병기 규칙을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from hub.app.dtos.bookmark_directory_dto import BookmarkedStock
from hub.app.dtos.news_alert_dto import AlertableNews
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.use_cases.news_alert_scan_interactor import NewsAlertScanInteractor

_NOW = datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc)


class _StubFeed:
    def __init__(self, items: list[AlertableNews]):
        self.items = items
        self.calls: list[float] = []

    async def pull_alertable(self, min_abs_sentiment: float, limit: int = 200):
        self.calls.append(min_abs_sentiment)
        return self.items


class _StubBookmarks:
    def __init__(self, rows: list[BookmarkedStock], telegrams: dict[int, str] | None = None):
        self.rows = rows
        self.telegrams = telegrams or {}

    async def stock_bookmarks(self):
        return self.rows

    async def area_bookmarks(self):
        return []

    async def telegram_chat_ids(self, user_ids):
        return {u: c for u, c in self.telegrams.items() if u in user_ids}


class _StubStatuses:
    def __init__(self, statuses: dict[str, StockStatusInfo] | None = None):
        self.statuses = statuses or {}

    async def latest_statuses(self, symbols):
        return {s: v for s, v in self.statuses.items() if s in symbols}

    async def latest_closes(self, symbols):
        return {}


class _StubContacts:
    def __init__(self, emails: dict[int, str]):
        self.emails = emails

    async def emails_by_ids(self, user_ids):
        return {u: e for u, e in self.emails.items() if u in user_ids}


def _news(ticker="005930.KS", sentiment=-0.7, title="반도체 급락 우려") -> AlertableNews:
    return AlertableNews(
        news_id=1, ticker=ticker, title=title, sentiment=sentiment,
        event_type="실적", published_at=_NOW,
    )


def _status(direction="DOWN") -> StockStatusInfo:
    return StockStatusInfo(
        ticker="005930.KS", as_of=_NOW, direction=direction,
        price=70000.0, change_pct=-0.02, up_rate=None, baseline_up_rate=None,
        ready=False, price_as_of=None,
    )


async def test_북마크한_종목의_강한_감성_뉴스만_사용자별로_묶인다():
    # 접미 흡수: 뉴스는 005930.KS, 북마크는 005930
    feed = _StubFeed([_news()])
    interactor = NewsAlertScanInteractor(
        feed=feed,
        bookmarks=_StubBookmarks([
            BookmarkedStock(user_id=1, ticker="005930", label="삼성전자"),
            BookmarkedStock(user_id=2, ticker="AAPL", label="애플"),
        ]),
        statuses=_StubStatuses({"005930.KS": _status()}),
        contacts=_StubContacts({1: "u1@example.com", 2: "u2@example.com"}),
    )
    report = await interactor.scan()

    assert feed.calls == [0.5]  # 임계는 인터랙터 상수(MIN_ABS_SENTIMENT)
    assert report.articles_found == 1
    assert report.bookmarks_matched == 1
    assert len(report.emails) == 1 and report.emails[0].to == "u1@example.com"
    body = report.emails[0].body
    assert "감성 -0.7(악재성)" in body
    assert "현재 신호 상태: 하락 신호" in body  # B9 차별점 — 신호 병기
    assert "매수·매도 권유가 아니며" in body


async def test_후보_뉴스가_없으면_조용히_끝난다():
    interactor = NewsAlertScanInteractor(
        feed=_StubFeed([]), bookmarks=_StubBookmarks([]),
        statuses=_StubStatuses(), contacts=_StubContacts({}),
    )
    report = await interactor.scan()
    assert report.articles_found == 0 and report.emails == []


async def test_스냅샷_없는_종목은_신호_라인_없이_나간다():  # 열화 동작
    interactor = NewsAlertScanInteractor(
        feed=_StubFeed([_news()]),
        bookmarks=_StubBookmarks([BookmarkedStock(user_id=1, ticker="005930", label="삼성전자")]),
        statuses=_StubStatuses({}),
        contacts=_StubContacts({1: "u1@example.com"}),
    )
    report = await interactor.scan()
    assert len(report.emails) == 1
    assert "현재 신호 상태" not in report.emails[0].body
