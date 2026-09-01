"""PriceAlertScanInteractor 테스트 — 스텁 포트로 판정·one-shot·채널 보류 규칙을 고정한다."""
from __future__ import annotations

from hub.app.dtos.price_alert_scan_dto import ActivePriceAlert
from hub.app.use_cases.price_alert_scan_interactor import PriceAlertScanInteractor


class _StubAlerts:
    def __init__(self, alerts: list[ActivePriceAlert], telegrams: dict[int, str] | None = None):
        self.alerts = alerts
        self.telegrams = telegrams or {}
        self.triggered: list[int] = []

    async def active_alerts(self) -> list[ActivePriceAlert]:
        return self.alerts

    async def mark_triggered(self, alert_ids: list[int]) -> None:
        self.triggered.extend(alert_ids)

    async def telegram_chat_ids(self, user_ids: list[int]) -> dict[int, str]:
        return {u: c for u, c in self.telegrams.items() if u in user_ids}


class _StubStatuses:
    def __init__(self, closes: dict[str, float]):
        self.closes = closes

    async def latest_statuses(self, symbols):
        return {}

    async def latest_closes(self, symbols: list[str]) -> dict[str, float]:
        return {s: v for s, v in self.closes.items() if s in symbols}


class _StubContacts:
    def __init__(self, emails: dict[int, str]):
        self.emails = emails

    async def emails_by_ids(self, user_ids: list[int]) -> dict[int, str]:
        return {u: e for u, e in self.emails.items() if u in user_ids}


def _alert(alert_id=1, user_id=1, ticker="005930", target=70000.0, direction="above"):
    return ActivePriceAlert(
        alert_id=alert_id, user_id=user_id, ticker=ticker,
        target_price=target, direction=direction,
    )


async def test_도달한_조건만_통지하고_비활성화한다():
    alerts = _StubAlerts([
        _alert(alert_id=1, ticker="005930", target=70000, direction="above"),   # 도달(71000)
        _alert(alert_id=2, ticker="005930", target=60000, direction="below"),   # 미도달
        _alert(alert_id=3, ticker="AAPL", target=200, direction="below"),       # 도달(180)
    ])
    interactor = PriceAlertScanInteractor(
        alerts=alerts,
        statuses=_StubStatuses({"005930": 71000.0, "AAPL": 180.0}),
        contacts=_StubContacts({1: "u1@example.com"}),
    )
    report = await interactor.scan()

    assert report.alerts_scanned == 3 and report.triggered == 2
    assert sorted(alerts.triggered) == [1, 3]  # one-shot — 통지분만 비활성화
    assert len(report.emails) == 1
    body = report.emails[0].body
    assert "005930: 설정선 70,000원(이상) 도달 — 최근 수집가 71,000원" in body
    assert "AAPL: 설정선 200.00달러(이하) 도달 — 최근 수집가 180.00달러" in body
    assert "매수·매도 권유가 아닙니다" in body  # 사실 통지 규범


async def test_봉_없는_심볼은_보류하고_다음_스캔으로_넘긴다():
    alerts = _StubAlerts([_alert(ticker="UNKNOWN", target=10, direction="above")])
    interactor = PriceAlertScanInteractor(
        alerts=alerts, statuses=_StubStatuses({}),
        contacts=_StubContacts({1: "u1@example.com"}),
    )
    report = await interactor.scan()
    assert report.triggered == 0 and alerts.triggered == []


async def test_채널_없는_회원의_도달_조건은_비활성화하지_않는다():
    # 채널이 생기면 다음 스캔에서 통지된다(bookmark의 상태 미기록 규칙과 같은 결)
    alerts = _StubAlerts([_alert(user_id=9, target=1, direction="above")])
    interactor = PriceAlertScanInteractor(
        alerts=alerts, statuses=_StubStatuses({"005930": 71000.0}),
        contacts=_StubContacts({}),
    )
    report = await interactor.scan()
    assert report.triggered == 0 and alerts.triggered == []
    assert report.emails == [] and report.telegrams == []


async def test_텔레그램만_등록한_회원도_통지된다():
    alerts = _StubAlerts(
        [_alert(user_id=2, target=1, direction="above")], telegrams={2: "chat-2"},
    )
    interactor = PriceAlertScanInteractor(
        alerts=alerts, statuses=_StubStatuses({"005930": 71000.0}),
        contacts=_StubContacts({}),
    )
    report = await interactor.scan()
    assert report.triggered == 1 and alerts.triggered == [1]
    assert report.emails == [] and len(report.telegrams) == 1
    assert report.telegrams[0].chat_id == "chat-2"
