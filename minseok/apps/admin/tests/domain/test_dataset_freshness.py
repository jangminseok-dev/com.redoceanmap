from datetime import UTC, datetime, timedelta

from admin.domain.services.dataset_freshness import (
    SCHEDULES,
    FreshnessState,
    evaluate,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _at(delta: timedelta) -> datetime:
    return NOW - delta


def test_주기_없는_데이터셋은_판정하지_않는다():
    for key in ("trade_area", "estimated_sales", "store", "recommendations"):
        v = evaluate(key, _at(timedelta(days=365)), NOW)
        assert v.state is FreshnessState.UNSCHEDULED
        assert v.expected is None
        assert v.age_seconds is None


def test_주기_있는데_적재_이력이_없으면_불명():
    v = evaluate("news_articles", None, NOW)
    assert v.state is FreshnessState.UNKNOWN
    assert v.expected == "30분마다"
    assert v.age_seconds is None


def test_기대_주기_안이면_정상():
    v = evaluate("news_articles", _at(timedelta(minutes=25)), NOW)
    assert v.state is FreshnessState.FRESH
    assert v.age_seconds == 25 * 60


def test_late_after_경계():
    late = SCHEDULES["news_articles"].late_after
    assert evaluate("news_articles", _at(late), NOW).state is FreshnessState.FRESH
    assert (
        evaluate("news_articles", _at(late + timedelta(seconds=1)), NOW).state
        is FreshnessState.LATE
    )


def test_stale_after_경계():
    stale = SCHEDULES["news_articles"].stale_after
    assert evaluate("news_articles", _at(stale), NOW).state is FreshnessState.LATE
    assert (
        evaluate("news_articles", _at(stale + timedelta(seconds=1)), NOW).state
        is FreshnessState.STALE
    )


def test_미래_시각은_나이_0으로_클램프():
    v = evaluate("news_articles", NOW + timedelta(hours=5), NOW)
    assert v.state is FreshnessState.FRESH
    assert v.age_seconds == 0


def test_2일_정지_회귀_2026_07_25_사고():
    """PC가 2일 넘게 꺼져 수집이 멈춘 상황 — 30분 주기 뉴스가 '정지'로 떠야 한다."""
    v = evaluate("news_articles", _at(timedelta(days=2, hours=6)), NOW)
    assert v.state is FreshnessState.STALE


def test_주말_휴장에_주가봉과_예측스냅샷은_오탐하지_않는다():
    """미국 종목은 금요일 종가 이후 화요일 새벽까지 신규 봉이 없다 — 정상이어야 한다."""
    weekend = timedelta(days=3, hours=6)
    assert evaluate("price_bars", _at(weekend), NOW).state is FreshnessState.FRESH
    assert evaluate("forecast_snapshots", _at(weekend), NOW).state is FreshnessState.FRESH
